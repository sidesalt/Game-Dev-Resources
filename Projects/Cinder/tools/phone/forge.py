"""Forge: the AI designs a brand new Cinderdeep monster and writes it as a
voxel recipe in assets/recipes/, in the same style as cinder_hound.gd.

    1. concept  the AI invents a monster (or takes your idea) and plans it
    2. write    the AI writes the GDScript recipe from the plan
    3. check    safety and API checks, plus gdparse and Godot when installed
    4. fix      problems are sent back to the AI, up to a few times
    5. polish   one more pass that adds detail, kept only if it still passes

Only ever uses free ($0) models: GitHub Models first (free with the GitHub
token, nothing to sign up for), then OpenRouter's :free models and Ollama
Cloud's free models when a key is set, then the local Ollama model. Only uses Python's standard library.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request

# Free models move around a lot, so these are preferences, not requirements:
# the first one that answers is used. OpenRouter's list is read live.
OLLAMA_CLOUD_MODELS = ["gpt-oss:120b", "gemma4:31b", "nemotron-3-ultra", "qwen3-coder:480b", "deepseek-v4-flash"]
OPENROUTER_LIKES = ["qwen3-coder", "gpt-oss-120b", "nemotron", "deepseek", "gemma-4", "llama-4", "glm", "kimi"]

GITHUB_LIKES = ["openai/gpt-4.1", "deepseek/deepseek-v3-0324", "openai/gpt-4o", "meta/llama-4-maverick-17b-128e-instruct-fp8",
                "mistral-ai/codestral-2501", "openai/gpt-4.1-mini"]

PROVIDERS = [
    # Free tier: about 50 requests a day, 8k tokens in and 4k out per request.
    {"name": "GitHub Models", "url": "https://models.github.ai/inference", "key": "GITHUB_TOKEN",
     "models": "github-free", "max_tokens": 4000,
     "max_input_chars": 26000},
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


def has_cloud(cfg):
    return any(key_for(cfg, p["key"]) for p in PROVIDERS)


def _post(url, key, body, timeout):
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + key,
               "HTTP-Referer": "https://github.com/sidesalt/Game-Dev-Resources", "X-Title": "Cinderdeep"}
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


def github_free(key):
    """GitHub's model catalogue, strongest general models first. Reasoning
    models are skipped: their free limit is only a few requests a day."""
    try:
        req = urllib.request.Request("https://models.github.ai/catalog/models",
                                     headers={"Authorization": "Bearer " + key, "Accept": "application/json"})
        live = [m.get("id", "") for m in json.loads(urllib.request.urlopen(req, timeout=30).read())
                if m.get("rate_limit_tier") in ("high", "low")]
    except (urllib.error.URLError, OSError, ValueError, AttributeError):
        live = []
    if not live:
        return GITHUB_LIKES
    liked = [m for m in GITHUB_LIKES if m in live]
    return liked + [m for m in live if m not in liked and "embed" not in m][:4]


class Brain:
    """Talks to the best AI that is available, and remembers which one worked."""

    def __init__(self, cfg, local_chat, say):
        self.cfg, self.local_chat, self.say = cfg, local_chat, say
        self.working = None  # (provider, model) that last answered

    def candidates(self):
        if self.working:
            yield self.working
        for p in self.cfg.get("providers", []) + PROVIDERS:
            key = key_for(self.cfg, p["key"]) if p.get("key") else ""
            if p.get("key") and not key:
                continue
            models = p["models"]
            if models == "github-free":
                models = github_free(key)
            elif models == "openrouter-free":
                try:
                    models = openrouter_free(p["url"], key)
                except (urllib.error.URLError, OSError, ValueError) as error:
                    self.say("Could not list OpenRouter's free models (%s)." % error)
                    continue
            for model in models:
                yield (dict(p, key_value=key), model)

    def ask(self, system, user, temperature=0.6):
        for provider, model in self.candidates():
            if len(system) + len(user) > provider.get("max_input_chars", 10 ** 9):
                continue
            body = {"model": model, "temperature": temperature, "max_tokens": provider.get("max_tokens", 10000),
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
            try:
                reply = _post(provider["url"] + "/chat/completions", provider["key_value"], body, timeout=600)
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
        if self.cfg.get("make_local", not self.cfg.get("manage_ai")):
            model = self.cfg.get("make_model") or self.cfg["model"]
            self.say("No free cloud AI answered, using the local AI %s (slower, simpler results)." % model)
            return self.local_chat(model, system, user, temperature)
        raise ForgeError("No AI answered. Add a free OpenRouter or Ollama key (see ODYSSEUS.md).")


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
- Reply with only the complete file in one ```gdscript code block.""" % (MAX_AXIS, MIN_SHAPES)


def concept_prompt(root, existing, idea):
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
    return system, user


def code_prompt(root, plan, example=True):
    pal, _ = palette(root)
    hound = read(root, "assets", "recipes", "cinder_hound.gd") if example else "(same style as before)"
    system = ("You write GDScript 4 voxel recipes for the Cinderdeep game. You write correct, statically typed "
              "code that runs first time, and you make highly detailed, beautiful models.\n\n" + RULES)
    user = ("VoxelBuilder API:\n```gdscript\n%s\n```\n\nPalette:\n```gdscript\n%s\n```\n\n"
            "Example recipe (match its style and quality):\n```gdscript\n%s\n```\n\n"
            "Write the recipe for this monster:\n%s") % (api_reference(root), pal, hound, json.dumps(plan, indent=1))
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


def static_problems(code, ramps):
    """Plain checks that keep AI code safe and on the real API."""
    problems = []
    body = strip_strings(code)
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
    for name in sorted(set(re.findall(r"\b([A-Z][A-Za-z0-9_]*)\b", body))):
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
    shapes = sum(body.count(s) for s in SHAPES)
    if shapes < MIN_SHAPES:
        problems.append("Only %d shape calls. Add much more detail: at least %d (horns, claws, plates, teeth, "
                        "spikes, cracks...)." % (shapes, MIN_SHAPES))
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
    godot = cfg.get("godot") or os.environ.get("GODOT") or shutil.which("godot") or shutil.which("godot4")
    if not godot:
        return None
    subprocess.run([godot, "--headless", "--path", root, "--import"], capture_output=True, timeout=600)
    result = subprocess.run([godot, "--headless", "--path", root, "--script", "res://tools/bake.gd", "--",
                             "--force", "--only=" + name], capture_output=True, text=True, timeout=600)
    log = result.stdout + result.stderr
    built = re.search(r"recipe %s -> .* \((\d+) voxels" % re.escape(name), log)
    if built and int(built.group(1)) >= 1500:
        return []
    if built:
        return ["The model only has %s voxels. Make it bigger and much more detailed." % built.group(1)]
    errors = [line.strip() for line in log.splitlines() if "ERROR" in line or "error" in line.lower()]
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


def finish(code, plan):
    """Puts our own header on the file so every AI recipe looks the same."""
    lines = code.splitlines()
    rest = [line for line in lines[1:] if not line.startswith("##")] if lines else []
    while rest and not rest[0].strip():
        rest.pop(0)
    return "extends RefCounted\n%s\n\n%s\n" % (header(plan), "\n".join(rest).rstrip())


def forge(cfg, root, brain, existing, idea, say, tries=4):
    """Returns (name, title, code) for a new recipe that passed every check."""
    _, ramps = palette(root)
    say("Designing a new monster...")
    plan = extract_json(brain.ask(*concept_prompt(root, existing, idea), temperature=0.9))
    names = set(f[:-3] for f in os.listdir(os.path.join(root, "assets", "recipes")) if f.endswith(".gd"))
    name = clean_name(plan.get("name") or plan.get("title"), names)
    plan["name"] = name
    say("Idea: %s - %s" % (plan.get("title", name), plan.get("look", "")[:200]))

    system, user = code_prompt(root, plan)
    lean = code_prompt(root, plan, example=False)[1]  # fix rounds: room for the last version instead
    say("Writing the voxel recipe...")
    reply = brain.ask(system, user, temperature=0.4)
    good = None
    for attempt in range(tries):
        code = finish(extract_code(reply), plan)
        problems = static_problems(code, ramps) or gdparse_problems(code)
        if not problems:
            problems = check_in_godot(cfg, root, name, code)
        if not problems:
            good = code
            break
        say("  Check %d found %d problem(s), asking the AI to fix them." % (attempt + 1, len(problems)))
        reply = brain.ask(system, lean + "\n\nYour last version:\n```gdscript\n%s```\n\nFix these problems and "
                          "reply with the whole corrected file:\n- %s" % (code, "\n- ".join(problems)), temperature=0.3)
    if not good:
        raise ForgeError("The AI could not write a working %s after %d tries, so nothing was saved." % (name, tries))

    say("Polishing: adding more detail...")
    polished = brain.ask(system, lean + "\n\nThis version works:\n```gdscript\n%s```\n\nMake it more detailed and "
                         "more striking without breaking any rule: more secondary forms, finer surface detail, "
                         "better colour variation and glow. Reply with the whole file." % good, temperature=0.4)
    better = finish(extract_code(polished), plan)
    if not (static_problems(better, ramps) or gdparse_problems(better) or check_in_godot(cfg, root, name, better)):
        good = better
    else:
        say("  The polished version had problems, keeping the working one.")
    return name, plan.get("title", name), good


def check_in_godot(cfg, root, name, code):
    path = os.path.join(root, "assets", "recipes", name + ".gd")
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        problems = godot_problems(cfg, root, name)
    finally:
        os.remove(path)
        for leftover in (os.path.join(root, "assets", "vox", name + ".vox"),
                         os.path.join(root, "assets", "scenes", name + ".tscn")):
            if os.path.exists(leftover):
                os.remove(leftover)
    return problems or []
