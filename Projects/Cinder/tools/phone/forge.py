"""Forge: the AI designs a brand new Cinderdeep monster and writes it as a
voxel recipe in assets/recipes/, in the same style as cinder_hound.gd.

    1. concept  the AI invents a monster (or takes your idea) and plans it
    2. write    the AI writes the GDScript recipe from the plan
    3. check    safety and API checks, plus gdparse and Godot when installed
    4. fix      problems are sent back to the AI, up to a few times
    5. polish   one more pass that adds detail, kept only if it still passes

Only ever uses free ($0) models: OVHcloud AI Endpoints first (a free tier
with no key or sign-up), then OpenRouter's :free models and Ollama Cloud's
free models when a key is set, then the local Ollama model. Only uses Python's standard library.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

# Free models move around a lot, so these are preferences, not requirements:
# the first one that answers is used. OpenRouter's list is read live.
OLLAMA_CLOUD_MODELS = ["gpt-oss:120b", "nemotron-3-ultra", "nemotron-3-super", "gemma4:31b", "gpt-oss:20b"]  # free 2026-10-12
OPENROUTER_LIKES = ["qwen3-coder", "gpt-oss-120b", "nemotron", "deepseek", "gemma-4", "llama-4", "glm", "kimi"]

OVH_LIKES = ["gpt-oss-120b", "Qwen3.5-397B-A17B", "Qwen3.8-27B", "Qwen3.6-27B", "Meta-Llama-3_3-70B-Instruct",
             "Mistral-Small-3.2-24B-Instruct-2506"]

PROVIDERS = [
    # Anonymous free tier: no key, about 2 requests a minute per model.
    {"name": "OVHcloud", "url": "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1", "key": None, "models": "ovh-free"},
    {"name": "OpenRouter", "url": "https://openrouter.ai/api/v1", "key": "OPENROUTER_API_KEY", "models": "openrouter-free"},
    {"name": "Ollama Cloud", "url": "https://ollama.com/v1", "key": "OLLAMA_API_KEY", "models": OLLAMA_CLOUD_MODELS},
]

MARKER = "## Made by Cinder AI."
MAX_AXIS = 96
MIN_SHAPES = 18

# Names a recipe may use that start with a capital letter. Anything else
# (OS, FileAccess, ClassDB...) is refused, so AI code can only build voxels.
ALLOWED_TYPES = {
    "Vector2", "Vector2i", "Vector3", "Vector3i", "Color", "VoxelBuilder", "VoxelModel", "CinderPalette",
    "PackedInt32Array", "PackedFloat32Array", "PackedVector3Array", "Array", "Dictionary", "RefCounted",
    "PI", "TAU", "INF",
}
# Object methods that reach other code by name.
BLOCKED_METHODS = {
    "callv", "call_deferred", "set_script", "connect", "emit_signal", "set_deferred", "set", "set_indexed",
    "free", "notification", "set_meta", "add_user_signal", "propagate_call",
}
BLOCKED_CALLS = {
    "load", "preload", "str_to_var", "bytes_to_var", "bytes_to_var_with_objects", "instance_from_id",
    "get_tree", "get_node", "callv", "call_deferred", "set_script", "get_script", "new_script", "inst_to_dict",
    "dict_to_inst", "type_convert", "convert", "print_rich", "push_error", "push_warning",
}
BUILDER_METHODS = {
    "mat", "ramp", "pick", "n01", "noisy", "paint_at", "set_v", "get_v", "solid", "exposed", "on_surface",
    "box", "ellipsoid", "tube", "column", "line", "recolor", "shade", "mirror_x", "erode", "remove_floating",
}
BUILDER_FIELDS = {"model", "rng", "noise"}
SHAPES = ("b.ellipsoid(", "b.tube(", "b.box(", "b.column(", "b.line(", "b.set_v(")


class ForgeError(RuntimeError):
    pass


# ---------------------------------------------------------------- AI access

def key_for(cfg, name):
    return os.environ.get(name) or cfg.get("keys", {}).get(name, "")


def godot_path(cfg):
    return cfg.get("godot") or os.environ.get("GODOT") or shutil.which("godot") or shutil.which("godot4")


def _post(url, key, body, timeout):
    headers = {"Content-Type": "application/json", "HTTP-Referer": "https://github.com/sidesalt/Game-Dev-Resources", "X-Title": "Cinderdeep"}
    if key:
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def openrouter_free(url, key):
    """The live list of free OpenRouter models, the most capable first."""
    req = urllib.request.Request(url + "/models", headers={"Authorization": "Bearer " + key})
    data = json.loads(urllib.request.urlopen(req, timeout=30).read()).get("data", [])
    free = [m for m in data if m.get("id", "").endswith(":free")
            and str(m.get("pricing", {}).get("prompt", "1")) in ("0", "0.0")]

    def rank(m):
        mid = m["id"].lower()
        liked = next((i for i, word in enumerate(OPENROUTER_LIKES) if word in mid), len(OPENROUTER_LIKES))
        return (liked, -int(m.get("context_length") or 0))
    return [m["id"] for m in sorted(free, key=rank)][:6]


def ovh_free(url):
    """OVHcloud's live chat models, the preferred ones first."""
    try:
        data = json.loads(urllib.request.urlopen(url + "/models", timeout=30).read()).get("data", [])
        live = [m.get("id", "") for m in data]
    except (urllib.error.URLError, OSError, ValueError, AttributeError):
        return OVH_LIKES
    return [m for m in OVH_LIKES if m in live] or OVH_LIKES


class Brain:
    """Talks to the best AI that is available, and remembers which one worked."""

    def __init__(self, cfg, local_chat, say, team=None):
        self.cfg, self.local_chat, self.say = cfg, local_chat, say
        self.team = team or {}
        self.working = None  # (provider, model) that last answered

    def candidates(self):
        if self.working:
            yield self.working
        order = self.team.get("providers", [])
        providers = sorted(self.cfg.get("providers", []) + PROVIDERS,
                           key=lambda p: order.index(p["name"]) if p["name"] in order else len(order))
        liked = self.team.get("models", [])
        for p in providers:
            key = key_for(self.cfg, p["key"]) if p.get("key") else ""
            if p.get("key") and not key:
                continue
            models = p["models"]
            if models == "ovh-free":
                models = ovh_free(p["url"])
            elif models == "openrouter-free":
                try:
                    models = openrouter_free(p["url"], key)
                except (urllib.error.URLError, OSError, ValueError) as error:
                    self.say("Could not list OpenRouter's free models (%s)." % error)
                    continue
            models = [m for m in liked if m in models] + [m for m in models if m not in liked]
            for model in models:
                yield (dict(p, key_value=key), model)

    def _post_patiently(self, provider, body):
        """Free tiers allow a few requests a minute: on "too many", wait and retry."""
        for wait in (35, 65, 0):
            try:
                return _post(provider["url"] + "/chat/completions", provider["key_value"], body, timeout=900)
            except urllib.error.HTTPError as error:
                if error.code != 429 or not wait:
                    raise
                self.say("  %s is busy, waiting %d seconds..." % (provider["name"], wait))
                time.sleep(wait)

    def ask(self, system, user, temperature=0.6):
        for provider, model in self.candidates():
            if len(system) + len(user) > provider.get("max_input_chars", 10 ** 9):
                continue
            body = {"model": model, "temperature": temperature, "max_tokens": provider.get("max_tokens", 10000),
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
            try:
                reply = self._post_patiently(provider, body)
                text = (reply.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            except urllib.error.HTTPError as error:
                self.say("  %s %s said no (%d), trying the next one." % (provider["name"], model, error.code))
                if self.working == (provider, model):
                    self.working = None
                continue
            except (urllib.error.URLError, OSError, ValueError) as error:
                self.say("  %s %s did not answer (%s)." % (provider["name"], model, error))
                continue
            if text.strip():
                if self.working != (provider, model):
                    self.say("Using %s: %s" % (provider["name"], model))
                self.working = (provider, model)
                return text.strip()
        if not self.cfg.get("cloud_only", True) and self.cfg.get("make_local", not self.cfg.get("manage_ai")):
            model = self.cfg.get("make_model") or self.cfg["model"]
            self.say("No free cloud AI answered, using the local AI %s (slower, simpler results)." % model)
            return self.local_chat(model, system, user, temperature)
        raise ForgeError("No free AI answered right now. Try again later, or add a free OpenRouter or Ollama key "
                         "(see ODYSSEUS.md).")


# ---------------------------------------------------------------- prompts

def api_reference(root):
    """Signatures and doc comments of VoxelBuilder, read from the source so the
    AI always sees the real API."""
    out, docs = [], []
    with open(os.path.join(root, "addons", "cinder_voxel", "voxel_builder.gd"), encoding="utf-8") as f:
        for line in f:
            if line.startswith("##"):
                docs.append(line.rstrip())
            elif line.startswith("func ") and not line.startswith("func _"):
                out.extend(docs + [line.rstrip().rstrip(":")])
                docs = []
            elif not line.strip().startswith("#"):
                docs = []
    return "\n".join(out)


def palette(root):
    with open(os.path.join(root, "assets", "cinder_palette.gd"), encoding="utf-8") as f:
        text = f.read()
    return text, set(re.findall(r"^const (\w+)", text, re.M))


def ramp_counts(root):
    text, _ = palette(root)
    return {name: len(re.findall(r'"#', body)) for name, body in re.findall(r"^const (\w+) := \[(.*?)\]", text, re.M)}


def ramp_sizes(root):
    """How many colours each CinderPalette ramp has, e.g. "EMBER 6 (index 0-5)"."""
    return ", ".join("%s %d (index 0-%d)" % (name, n, n - 1) for name, n in ramp_counts(root).items())


def read(root, *parts):
    with open(os.path.join(root, *parts), encoding="utf-8") as f:
        return f.read()


RULES = """Rules for the recipe file:
- Exactly this shape: `extends RefCounted`, `##` comment lines describing the monster, `const SEED := <number>`,
  then `static func build(seed := SEED) -> VoxelModel:` that ends with `return b.model`.
- Make the builder with `var b := VoxelBuilder.new(Vector3i(X, Y, Z), seed)`. Each side at most %d.
  Y is up, the monster faces +Z and stands on y = 0, centred in X.
- Only use the VoxelBuilder API below, CinderPalette ramps, Vector3/Vector3i/Color maths, local lambdas
  (`func(p: Vector3i) -> int:`) and `for` loops. No while loops, no load/preload, no files, no other classes.
- Colours come from CinderPalette ramps via b.ramp(...). Glowing parts use an emission list, like the hound's ember.
- Highly detailed: build big forms first (body masses), then secondary forms (limbs, head, armour plates,
  horns, wings, tail), then fine detail (claws, teeth, eyes, cracks, spikes, rivets, drips). Use at least %d
  shape calls; loops over `[-1.0, 1.0]` for left/right pairs. Paint with noise-driven lambdas, finish with
  b.shade(...) up and down passes and a b.recolor(...) pass for glowing cracks or markings, and bright eyes.
- Keep it readable from far away: a strong silhouette, dark soot/ash body, ember/flame/lava accents.
- Every part must touch the body (no floating pieces). Keep static typing like the example.
- Indent with tabs only. Type loop variables (`for side: float in [-1.0, 1.0]:`); `:=` only works when the value
  has a known type, otherwise write the type (`var x: float = cx + side * 3.0`).
- Reply with only the complete file in one ```gdscript code block.""" % (MAX_AXIS, MIN_SHAPES)


def concept_prompt(root, existing, idea, team=None):
    design = read(root, "docs", "CINDERDEEP_GAME_DESIGN.md")[:6000]
    system = ("You are the lead creature designer for Cinderdeep, a dark ember-and-ash soulslike fantasy game with "
              "a voxel art style. You invent monsters that are memorable, readable and fun to fight.")
    user = (
        "Game notes:\n%s\n\nMonsters and props that already exist (do not repeat them):\n%s\n\n"
        "%s\n\nReply with JSON only:\n"
        '{"name": "snake_case_file_name", "title": "Display Name", "region": "where it lives",\n'
        ' "look": "2-4 sentences: silhouette, materials, colours, what glows",\n'
        ' "behaviour": "1 sentence: how it fights",\n'
        ' "grid": [x, y, z], "ramps": ["CinderPalette ramp names"],\n'
        ' "parts": ["10-20 concrete build steps, big forms first, with rough voxel positions and sizes"]}'
    ) % (design, existing, ("The player asked for: " + idea) if idea else
         "Invent one new monster that fits the world and is different from those above.")
    if team:
        user += ("\n\nYou design for %s. Their job: %s Grid size: %s."
                 % (team.get("name", "the team"), team.get("job", ""), team.get("grid", "")))
    return system, user


def guide(root):
    """docs/VOXEL_ASSET_GUIDE.md: the art direction the AI is coached with."""
    try:
        return read(root, "docs", "VOXEL_ASSET_GUIDE.md").split("\n", 2)[-1]
    except OSError:
        return ""


def code_prompt(root, plan, example=True):
    pal, _ = palette(root)
    hound = read(root, "assets", "recipes", "cinder_hound.gd") if example else "(same style as before)"
    system = ("You write GDScript 4 voxel recipes for the Cinderdeep game. You write correct, statically typed "
              "code that runs first time, and you make highly detailed, beautiful models.\n\n" + RULES
              + "\n\nAsset guide from the art director (follow it closely):\n" + guide(root))
    user = ("VoxelBuilder API:\n```gdscript\n%s\n```\n\nPalette:\n```gdscript\n%s\n```\n\n"
            "Ramp sizes. A ramp's colours are numbered from 0, never use a higher number, and an emission list "
            "must have exactly one value per colour: %s\n\n"
            "Example recipe (match its style and quality):\n```gdscript\n%s\n```\n\n"
            "Write the recipe for this monster:\n%s") % (api_reference(root), pal, ramp_sizes(root), hound,
                                                         json.dumps(plan, indent=1))
    return system, user


# ---------------------------------------------------------------- checks

def extract_code(text):
    blocks = re.findall(r"```(?:gdscript|gd|godot)?\s*\n(.*?)```", text, re.S)
    code = max(blocks, key=len) if blocks else text
    return code.strip().replace("\r\n", "\n") + "\n"


def extract_json(text):
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ForgeError("The AI's plan was not readable.")
    return json.loads(match.group(0))


def strip_strings(code):
    code = re.sub(r'"(?:[^"\\\n]|\\.)*"', '""', code)
    return "\n".join(line.split("#", 1)[0] for line in code.splitlines())


def static_problems(code, ramps, sizes=None):
    """Plain checks that keep AI code safe and on the real API. `sizes` maps a
    palette ramp to its number of colours, to catch out-of-range indexes."""
    problems = []
    body = strip_strings(code)
    for var, ramp, emission in re.findall(r"var (\w+)\s*:?=\s*b\.ramp\(CinderPalette\.(\w+)\s*(?:,\s*\[([^\]]*)\])?", body):
        n = (sizes or {}).get(ramp)
        if not n:
            continue
        if emission and len([e for e in emission.split(",") if e.strip()]) < n:
            problems.append("The emission list for `%s` needs %d values (CinderPalette.%s has %d colours)."
                            % (var, n, ramp, n))
        for index in set(re.findall(r"\b%s\[(\d+)\]" % re.escape(var), body)):
            if int(index) >= n:
                problems.append("`%s[%s]` is out of range: CinderPalette.%s has %d colours (0-%d)."
                                % (var, index, ramp, n, n - 1))
    if not code.lstrip().startswith("extends RefCounted"):
        problems.append("The file must start with `extends RefCounted`.")
    if not re.search(r"^const SEED := \d+", code, re.M):
        problems.append("Add `const SEED := <number>` at the top level.")
    if "static func build(seed := SEED) -> VoxelModel:" not in code:
        problems.append("The entry point must be exactly `static func build(seed := SEED) -> VoxelModel:`.")
    if not re.search(r"^\treturn b\.model\s*$", code, re.M):
        problems.append("build() must end with `return b.model` (one tab indent).")
    size = re.search(r"VoxelBuilder\.new\(Vector3i\((\d+),\s*(\d+),\s*(\d+)\)", code)
    if not size:
        problems.append("Create the builder with `VoxelBuilder.new(Vector3i(X, Y, Z), seed)` using plain numbers.")
    elif any(not 8 <= int(n) <= MAX_AXIS for n in size.groups()):
        problems.append("Each grid side must be between 8 and %d." % MAX_AXIS)
    if re.search(r"\bwhile\b", body):
        problems.append("Do not use while loops; use for loops.")
    if re.search(r"\.call\(\s*[\"&]", code):
        problems.append("Only call lambdas with `.call(p)`, never by method name.")
    for name in sorted(set(re.findall(r"\.([a-z_]\w*)\s*\(", body)) & BLOCKED_METHODS):
        problems.append("`.%s()` is not allowed in a recipe." % name)
    if "@" in body:
        problems.append("Do not use annotations such as @tool or @export.")
    if re.search(r"\bCallable\s*\(", body):
        problems.append("Do not construct `Callable(...)`; use lambdas (`func(p: Vector3i) -> int:`).")
    # `Callable` is fine as a type label (var paint: Callable = func...), never as a call.
    for name in sorted(set(re.findall(r"\b([A-Z][A-Za-z0-9_]*)\b", re.sub(r"(?<=[:>])\s*Callable\b", " ", body)))):
        if name in ALLOWED_TYPES or re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
            continue
        problems.append("`%s` is not allowed in a recipe. Use only VoxelBuilder, CinderPalette and vector maths." % name)
    for name in sorted(set(re.findall(r"(?<![.\w])([a-z_][a-z0-9_]*)\s*\(", body)) & BLOCKED_CALLS):
        problems.append("`%s()` is not allowed in a recipe." % name)
    for name in sorted(set(re.findall(r"\bb\.([a-z_]\w*)", body)) - BUILDER_METHODS - BUILDER_FIELDS):
        problems.append("`b.%s` does not exist. VoxelBuilder has: %s." % (name, ", ".join(sorted(BUILDER_METHODS))))
    for name in sorted(set(re.findall(r"CinderPalette\.(\w+)", body)) - ramps):
        problems.append("`CinderPalette.%s` does not exist. Ramps: %s." % (name, ", ".join(sorted(ramps))))
    for word in ("OS.", "FileAccess", "DirAccess", "Engine.", "ClassDB", "JavaScriptBridge", "Expression"):
        if word in body:
            problems.append("`%s` is not allowed in a recipe." % word.rstrip("."))
    for name in sorted(set(re.findall(r"var (\w+)\s*:?=\s*b\.ramp\(", body))):
        # A ramp is a list of colours; shapes need one colour or a painter lambda.
        if re.search(r"b\.(?:box|ellipsoid|tube|column|line|set_v)\((?:[^()]|\([^()]*\))*,\s*%s\s*(?:,[^,()]*)?\)" % name, body):
            problems.append("`%s` is a whole ramp used as paint. Use b.pick(%s, t, jitter) in a lambda or "
                            "b.noisy(%s) instead." % (name, name, name))
    if "b.remove_floating()" not in body:
        problems.append("Call `b.remove_floating()` after the last shape (before shading) so no stray voxels float.")
    shapes = sum(body.count(s) for s in SHAPES)
    if shapes < MIN_SHAPES:
        problems.append("Only %d shape calls. Add much more detail: at least %d (horns, claws, plates, teeth, "
                        "spikes, cracks...)." % (shapes, MIN_SHAPES))
    boxes, organic = body.count("b.box("), body.count("b.ellipsoid(") + body.count("b.tube(")
    if boxes > organic:
        problems.append("Too boxy (%d boxes, %d ellipsoids/tubes). Build bodies, heads and limbs from ellipsoids and "
                        "tapered tubes; keep boxes for armour plates and blades." % (boxes, organic))
    return list(dict.fromkeys(problems))


def gdparse_problems(code):
    tool = shutil.which("gdparse")
    if not tool:
        return []
    with tempfile.NamedTemporaryFile("w", suffix=".gd", delete=False, encoding="utf-8") as f:
        f.write(code)
    try:
        result = subprocess.run([tool, f.name], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(f.name)
    if result.returncode == 0:
        return []
    return ["GDScript syntax error: " + (result.stderr or result.stdout).strip().splitlines()[-1][:300]]


def godot_problems(cfg, root, name):
    """Builds the recipe for real when Godot is installed (GitHub always has it)."""
    godot = godot_path(cfg)
    if not godot:
        return None
    if not os.path.exists(os.path.join(root, ".godot", "global_script_class_cache.cfg")):
        subprocess.run([godot, "--headless", "--path", root, "--import"], capture_output=True, timeout=900)
    result = subprocess.run([godot, "--headless", "--path", root, "--script", "res://tools/bake.gd", "--",
                             "--force", "--only=" + name], capture_output=True, text=True, timeout=600)
    log = result.stdout + result.stderr
    built = re.search(r"recipe %s -> .* \((\d+) voxels" % re.escape(name), log)
    if built and int(built.group(1)) >= 1500:
        return []
    if built:
        return ["The model only has %s voxels. Make it bigger and much more detailed." % built.group(1)]
    # The real messages ("SCRIPT ERROR: Parse Error: ..."), not Godot's "at: file:line" pointers.
    errors = [line.strip() for line in log.splitlines()
              if "ERROR" in line and "FAILED " not in line and not line.strip().startswith("at:")]
    return ["Godot could not build it: " + " | ".join(errors[-4:])[:600]]


# ---------------------------------------------------------------- the forge

def clean_name(text, existing):
    name = re.sub(r"[^a-z0-9]+", "_", (text or "monster").lower()).strip("_")[:32] or "monster"
    base, n = name, 2
    while name in existing:
        name, n = "%s_%d" % (base, n), n + 1
    return name


def header(plan):
    lines = ["%s (%s). %s" % (plan.get("title", "Monster"), plan.get("region", "Cinderdeep"), plan.get("look", ""))]
    if plan.get("behaviour"):
        lines.append(plan["behaviour"])
    text = " ".join(lines)
    words, out, row = text.split(), [], "##"
    for word in words:
        if len(row) + len(word) > 110:
            out.append(row)
            row = "##"
        row += " " + word
    out.append(row)
    out.append(MARKER + " Faces +Z.")
    return "\n".join(out)


def tabs(code):
    """Godot refuses files that mix tabs and spaces, so indent with tabs only."""
    out = []
    for line in code.splitlines():
        body = line.lstrip(" \t")
        indent = line[:len(line) - len(body)].replace("\t", "    ")
        out.append("\t" * ((len(indent) + 2) // 4) + body if body else "")
    return "\n".join(out)


def finish(code, plan):
    """Puts our own header on the file so every AI recipe looks the same."""
    lines = tabs(code).splitlines()
    rest = [line for line in lines[1:] if not line.startswith("##")] if lines else []
    while rest and not rest[0].strip():
        rest.pop(0)
    return "extends RefCounted\n%s\n\n%s\n" % (header(plan), "\n".join(rest).rstrip())


def forge(cfg, root, brain, existing, idea, say, tries=4, team=None):
    """Returns (name, title, code) for a new recipe that passed every check."""
    _, ramps = palette(root)
    sizes = ramp_counts(root)
    say("Designing a new monster...")
    plan = extract_json(brain.ask(*concept_prompt(root, existing, idea, team), temperature=0.9))
    names = set(f[:-3] for f in os.listdir(os.path.join(root, "assets", "recipes")) if f.endswith(".gd"))
    name = clean_name(plan.get("name") or plan.get("title"), names)
    plan["name"] = name
    say("Idea: %s - %s" % (plan.get("title", name), plan.get("look", "")[:200]))

    system, user = code_prompt(root, plan)
    lean = code_prompt(root, plan, example=False)[1]  # fix rounds: room for the last version instead
    say("Writing the voxel recipe...")
    reply = brain.ask(system, user, temperature=0.4)
    good = last_bad = None
    for attempt in range(tries):
        code = finish(extract_code(reply), plan)
        problems = static_problems(code, ramps, sizes) or gdparse_problems(code)
        if not problems:
            problems = check_in_godot(cfg, root, name, code)
        if not problems:
            good = code
            break
        say("  Check %d found %d problem(s), asking the AI to fix them: %s" % (attempt + 1, len(problems),
                                                                         problems[0][:160]))
        last_bad = code
        reply = brain.ask(system, lean + "\n\nYour last version:\n```gdscript\n%s```\n\nFix these problems and "
                          "reply with the whole corrected file:\n- %s" % (code, "\n- ".join(problems)), temperature=0.3)
    if not good:
        try:  # kept for whoever improves the guide or the checks
            os.makedirs(os.path.join(os.path.expanduser("~"), ".cinder"), exist_ok=True)
            with open(os.path.join(os.path.expanduser("~"), ".cinder", "last_failed.gd"), "w", encoding="utf-8") as f:
                f.write(last_bad or "")
        except OSError:
            pass
        raise ForgeError("The AI could not write a working %s after %d tries, so nothing was saved." % (name, tries))

    say("Polishing: adding more detail...")
    polished = brain.ask(system, lean + "\n\nThis version works:\n```gdscript\n%s```\n\nMake it more detailed and "
                         "more striking without breaking any rule: more secondary forms, finer surface detail, "
                         "better colour variation and glow. Reply with the whole file." % good, temperature=0.4)
    better = finish(extract_code(polished), plan)
    issues = static_problems(better, ramps, sizes) or gdparse_problems(better) or check_in_godot(cfg, root, name, better)
    if not issues:
        good = better
    else:
        say("  The polished version had problems (%s), keeping the working one." % issues[0][:120])
    return name, plan.get("title", name), good


def check_in_godot(cfg, root, name, code):
    path = os.path.join(root, "assets", "recipes", name + ".gd")
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        problems = godot_problems(cfg, root, name)
    finally:
        os.remove(path)
        if os.path.exists(path + ".uid"):  # Godot adds one for every script it loads
            os.remove(path + ".uid")
        for leftover in (os.path.join(root, "assets", "vox", name + ".vox"),
                         os.path.join(root, "assets", "scenes", name + ".tscn")):
            if os.path.exists(leftover):
                os.remove(leftover)
    return problems or []
