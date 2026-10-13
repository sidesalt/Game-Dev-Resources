#!/usr/bin/env python3
"""Cinder phone AI: simple commands that let a small local AI keep improving
the Cinderdeep voxel assets.

    push        improve the next asset a little, save it to GitHub
    push 5      do that 5 times in a row
    ask TEXT    ask for a change, e.g.  ask make the hound glow more
    look        open the newest preview pictures
    undo        take back the last AI change
    status      show the last changes
    stop        stop the AI and free the phone's memory
    menu        number buttons for all of the above
    make        (on the phone: monster) the AI invents a new monster and writes its voxel recipe
    make 3      three new monsters
    make a lava golem with chains   a new monster from your idea
    serve       run as a chat model for Odysseus (type the commands in chat)

The AI may only change the safe settings in assets/tuning/<asset>.json, so it
can never break the game. GitHub rebuilds the 3D models and pictures itself.
Only uses Python's standard library.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import forge  # noqa: E402  (new monster recipes)

HOME = os.path.expanduser("~")
CONFIG_PATH = os.path.join(HOME, ".cinder", "config.json")
STATE_PATH = os.path.join(HOME, ".cinder", "state.json")
DEFAULTS = {
    "repo_dir": os.path.join(HOME, "Game-Dev-Resources"),
    "branch": "ccr-031f1132-nxzsb1",
    "github": "sidesalt/Game-Dev-Resources",
    "ai_url": "http://127.0.0.1:11434",
    "model": "qwen2.5:1.5b",
    "small_model": "qwen2.5:0.5b",
    # Phone: this tool starts/stops ollama itself. PC: Odysseus's stack owns it.
    "manage_ai": True,
    # Set to false for thinking models (qwen3.5, gpt-oss) so they answer directly.
    "think": None,
    "port": 8740,
    # Free cloud models only: never start or use local Ollama, so the PC's GPU
    # stays free for gaming. Set to false to allow the local AI again.
    "cloud_only": True,
}
# key: (default, min, max) — must match assets/tuning.gd
NUMBERS = {
    "scale": (1.0, 0.6, 1.6),
    "glow": (1.0, 0.0, 3.0),
    "brightness": (1.0, 0.6, 1.5),
    "tint_strength": (0.0, 0.0, 0.5),
    "saturation": (1.0, 0.4, 1.6),
    "wear": (0.0, 0.0, 0.25),
    "seed": (0, 0, 9999),
}
# One focus per round, so repeated pushes try different things.
FOCUS = [
    "glow balance: embers should pop without washing out the shape",
    "colour harmony with the ember-and-ash palette",
    "size and presence next to the other creatures",
    "weathered, battle-worn surface detail",
    "contrast and readability from far away",
    "a fresh variation of the shape",
]
DEFAULT_WISH = ("Make it look a little better and more dramatic for a dark ember-and-ash fantasy game, "
                "while keeping it easy to read. Change one to three settings by small amounts.")


# ---------------------------------------------------------------- helpers

SINK = [lambda text: print(text, flush=True)]
INTERACTIVE = [True]


def say(text):
    SINK[-1](text)


def load_json(path, fallback):
    try:
        with open(path, encoding="utf-8-sig") as f:  # -sig: Windows PowerShell adds a BOM
            return json.load(f)
    except (OSError, ValueError):
        return fallback


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def config():
    cfg = dict(DEFAULTS)
    cfg.update(load_json(CONFIG_PATH, {}))
    if os.environ.get("CINDER_REPO_DIR"):  # GitHub Actions
        cfg["repo_dir"] = os.environ["CINDER_REPO_DIR"]
    return cfg


def project(cfg):
    return os.path.join(cfg["repo_dir"], "Projects", "Cinder")


def git(cfg, *args, check=True):
    result = subprocess.run(["git", "-C", cfg["repo_dir"], *args], capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), result.stderr.strip()[-300:]))
    return result.stdout.strip()


def assets(cfg):
    folder = os.path.join(project(cfg), "assets", "recipes")
    return sorted(f[:-3] for f in os.listdir(folder) if f.endswith(".gd"))


def describe(cfg, asset):
    """The recipe's top comment: a plain description of the asset."""
    path = os.path.join(project(cfg), "assets", "recipes", asset + ".gd")
    lines = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("##"):
                lines.append(line[2:].strip())
            elif lines:
                break
    return " ".join(lines)[:600]


def free_memory_mb():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        pass
    return None


# ---------------------------------------------------------------- the AI

def ai_running(cfg):
    try:
        urllib.request.urlopen(cfg["ai_url"] + "/api/tags", timeout=3)
        return True
    except (urllib.error.URLError, OSError):
        return False


def start_ai(cfg):
    if cfg.get("cloud_only") or ai_running(cfg):
        return
    if not cfg["manage_ai"]:
        raise RuntimeError("Your local AI (Ollama) is not running. Start your AI PC stack first.")
    if not shutil.which("ollama"):
        raise RuntimeError("The AI (ollama) is not installed. Run the install line again.")
    say("Starting the AI...")
    env = dict(os.environ, OLLAMA_MAX_LOADED_MODELS="1", OLLAMA_NUM_PARALLEL="1", OLLAMA_KEEP_ALIVE="30s")
    log = open(os.path.join(HOME, ".cinder", "ai.log"), "a")
    subprocess.Popen(["ollama", "serve"], stdout=log, stderr=log, env=env, start_new_session=True)
    for _ in range(40):
        if ai_running(cfg):
            return
        time.sleep(0.5)
    raise RuntimeError("The AI did not start. Type: stop   then try again.")


def pick_model(cfg):
    """Use the smaller model when the phone is short on memory."""
    free = free_memory_mb()
    if cfg["manage_ai"] and free is not None and free < 1800:
        say("Phone memory is low (%d MB free), using the small AI." % free)
        return cfg["small_model"]
    return cfg["model"]


def ensure_model(cfg, model):
    tags = json.loads(urllib.request.urlopen(cfg["ai_url"] + "/api/tags", timeout=10).read())
    names = [m.get("name", "") for m in tags.get("models", [])]
    if model in names or model + ":latest" in names:
        return
    if not cfg["manage_ai"]:
        raise RuntimeError("The model %s is not installed on this PC." % model)
    say("Downloading the AI model %s (one time only)..." % model)
    subprocess.run(["ollama", "pull", model], check=True)


def chat(cfg, model, system, user, temperature, json_mode, num_ctx=2048):
    if cfg.get("cloud_only"):
        hint = "\n\nReply with one JSON object only, no other text." if json_mode else ""
        reply = brain(cfg).ask(system, user + hint, temperature)
        if json_mode:
            match = re.search(r"\{.*\}", reply, re.S)
            return match.group(0) if match else reply
        return reply
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False,
        "keep_alive": "30s",  # unload soon after, to give the memory back
        "options": {"num_ctx": num_ctx, "temperature": temperature},
    }
    if json_mode:
        body["format"] = "json"
    if cfg["think"] is not None:
        body["think"] = cfg["think"]
    req = urllib.request.Request(cfg["ai_url"] + "/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    reply = json.loads(urllib.request.urlopen(req, timeout=300 if num_ctx <= 2048 else 3600).read())
    return (reply.get("message", {}).get("content") or "").strip()


def history(cfg, asset):
    """The last few changes to this asset, so the AI doesn't repeat itself."""
    log = git(cfg, "log", "-3", "--format=%s", "--",
              "Projects/Cinder/assets/tuning/%s.json" % asset, check=False)
    notes = [line.split(" - ", 1)[-1] for line in log.splitlines() if " - " in line]
    return "; ".join(notes) or "none yet"


def make_brief(cfg, model, asset, current, wish, focus):
    """Step 1, the prompt generator: the AI writes its own clear instruction."""
    system = (
        "You are the art director of Cinderdeep, a dark fantasy voxel game of ember, ash and soot. "
        "Write ONE short instruction (at most 2 sentences) for a tuner who can ONLY change these settings: "
        "size (scale), glow strength, brightness, a colour tint and how strong it is, colour saturation, "
        "surface wear, and a variation seed. Name which settings to change and in which direction. "
        "Keep the model readable against a dark background. Reply with the instruction only.")
    user = ("Model: %s\nWhat it is: %s\nCurrent settings: %s\nRecent changes: %s\nGoal: %s\nFocus this time: %s"
            % (asset.replace("_", " "), describe(cfg, asset), json.dumps(current), history(cfg, asset), wish, focus))
    brief = chat(cfg, model, system, user, 0.8, False)
    brief = " ".join(brief.split())[:400]
    return brief or wish


def tune(cfg, model, asset, current, brief, temperature):
    """Step 2: follow the instruction, answering only with safe settings."""
    ranges = ", ".join("%s %s..%s" % (k, v[1], v[2]) for k, v in NUMBERS.items())
    system = (
        "You tune the look of ONE voxel 3D model. Follow the instruction. "
        "Reply with ONLY one JSON object with exactly these keys: "
        "scale, glow, brightness, tint, tint_strength, saturation, wear, seed, notes. "
        "Allowed ranges: " + ranges + ". tint is a colour like \"#ff7a2a\". "
        "seed 0 keeps the original shape; another number makes a new variation. "
        "Change only what the instruction asks, by small amounts. "
        "notes: what you changed, under 12 words.")
    user = "Current settings: %s\nInstruction: %s" % (json.dumps(current), brief)
    return chat(cfg, model, system, user, temperature, True)


def clean(raw, current):
    """Turn the AI's reply into safe settings, or None if it is unusable."""
    match = re.search(r"\{.*\}", raw or "", re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    out = dict(current)
    for key, (_, lo, hi) in NUMBERS.items():
        value = data.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = min(max(float(value), lo), hi)
            out[key] = int(value) if key == "seed" else round(value, 2)
    tint = data.get("tint")
    if isinstance(tint, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", tint.strip()):
        out["tint"] = tint.strip().lower()
    out["notes"] = str(data.get("notes", ""))[:120]
    changed = [k for k in NUMBERS if out[k] != current.get(k)] + (["tint"] if out["tint"] != current.get("tint") else [])
    return out if changed else None


# ---------------------------------------------------------------- commands

def improve(cfg, asset, wish, focus="whatever helps most"):
    path = os.path.join(project(cfg), "assets", "tuning", asset + ".json")
    current = {k: v[0] for k, v in NUMBERS.items()}
    current.update({"tint": "#ff7a2a", "notes": ""})
    current.update(load_json(path, {}))
    model = None
    if not cfg.get("cloud_only"):
        model = pick_model(cfg)
        ensure_model(cfg, model)
    name = asset.replace("_", " ")
    say("Writing a plan for %s..." % name)
    brief = make_brief(cfg, model, asset, current, wish, focus)
    say("Plan: " + brief)
    for temperature in (0.4, 0.8):
        result = clean(tune(cfg, model, asset, current, brief, temperature), current)
        if result:
            save_json(path, result)
            try:
                git(cfg, "add", path)
                git(cfg, "commit", "-q", "-m", "Cinder AI: %s - %s" % (asset, result["notes"] or "tweak"))
            except RuntimeError:
                git(cfg, "reset", "-q", check=False)
                git(cfg, "checkout", "-q", "--", path, check=False)
                raise
            changes = ", ".join("%s %s -> %s" % (k, current.get(k), result[k])
                                for k in list(NUMBERS) + ["tint"] if result[k] != current.get(k))
            say("Changed %s: %s (%s)" % (name, result["notes"] or "small tweak", changes))
            return True
    say("The AI's answer for %s was not usable, skipped it." % name)
    return False


def find_asset(names, text):
    words = text.lower()
    found = [a for a in names if any(part in words for part in a.split("_") if len(part) > 3)]
    return found[0] if len(found) == 1 else None


def sync(cfg):
    # Self-repair: drop half-finished AI edits and make sure commits have a name.
    git(cfg, "reset", "-q", check=False)
    git(cfg, "checkout", "-q", "--", "Projects/Cinder/assets/tuning", check=False)
    if not git(cfg, "config", "user.name", check=False):
        git(cfg, "config", "user.name", "Cinder Phone AI")
    if not git(cfg, "config", "user.email", check=False):
        git(cfg, "config", "user.email", "phone-ai@users.noreply.github.com")
    git(cfg, "checkout", "-q", cfg["branch"])
    git(cfg, "pull", "-q", "--rebase", "--autostash", "origin", cfg["branch"])


def publish(cfg):
    say("Saving to GitHub...")
    git(cfg, "push", "-q", "origin", cfg["branch"])
    say("Saved. New pictures appear on GitHub in about 5-10 minutes. Type: look")


def cmd_push(cfg, args):
    """push / push 5 / push hound / improve hound: plan, change, save."""
    rounds = next((min(int(a), 20) for a in args if a.isdigit()), 1)
    sync(cfg)
    names = assets(cfg)
    target = find_asset(names, " ".join(args))
    start_ai(cfg)
    state = load_json(STATE_PATH, {"next": 0, "focus": 0})
    done = 0
    for _ in range(rounds):
        if target:
            asset = target
        else:
            asset = names[state["next"] % len(names)]
            state["next"] += 1
        focus = FOCUS[state.get("focus", 0) % len(FOCUS)]
        state["focus"] = state.get("focus", 0) + 1
        save_json(STATE_PATH, state)
        done += improve(cfg, asset, DEFAULT_WISH, focus)
    if done:
        publish(cfg)


def cmd_ask(cfg, args):
    wish = " ".join(args).strip()
    if not wish and INTERACTIVE[0]:
        wish = input("What should change? ").strip()
    if not wish:
        say("Tell me what to change, for example:  ask make the hound glow more")
        return
    sync(cfg)
    names = assets(cfg)
    words = wish.lower()
    found = [a for a in names if any(part in words for part in a.split("_") if len(part) > 3)]
    if len(found) != 1:
        if not INTERACTIVE[0]:
            say("Which model? Say one of these names in your request:")
            say(", ".join(a.replace("_", " ") for a in names))
            return
        say("Which one?")
        for i, a in enumerate(names, 1):
            say("  %d  %s" % (i, a.replace("_", " ")))
        choice = input("Number: ").strip()
        if not choice.isdigit() or not 1 <= int(choice) <= len(names):
            say("Nothing changed.")
            return
        found = [names[int(choice) - 1]]
    start_ai(cfg)
    if improve(cfg, found[0], wish, "exactly what was asked"):
        publish(cfg)


BRAINS = {}


def team(cfg):
    """This device's team from teams.json (A, B or C), or {} if none is set."""
    teams = load_json(os.path.join(project(cfg), "teams.json"), {})
    return teams.get(str(cfg.get("team", "")).upper(), {})


def brain(cfg):
    """One shared Brain per run, so it remembers which free model answered."""
    if id(cfg) in BRAINS:
        return BRAINS[id(cfg)]

    def local_chat(model, system, user, temperature):
        start_ai(cfg)
        ensure_model(cfg, model)
        return chat(cfg, model, system, user, temperature, False, num_ctx=16384)
    BRAINS[id(cfg)] = forge.Brain(cfg, local_chat, say, team(cfg))
    return BRAINS[id(cfg)]


def existing_assets(cfg):
    return "\n".join("- %s: %s" % (a, describe(cfg, a)[:160]) for a in assets(cfg))


def make_here(cfg, ai, idea):
    """Designs, writes and checks one monster; commits it. Returns its name."""
    crew = team(cfg)
    name, title, code = forge.forge(cfg, project(cfg), ai, existing_assets(cfg), idea, say, team=crew)
    path = os.path.join(project(cfg), "assets", "recipes", name + ".gd")
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    git(cfg, "add", path)
    who = (" (%s)" % crew["name"]) if crew else ""
    git(cfg, "commit", "-q", "-m", "Cinder AI%s: new monster %s - %s" % (who, name, title))
    say("Made %s (%s)." % (title, name))
    return name


REQUESTS = os.path.join("assets", "requests")


def cmd_make(cfg, args):
    """make / make 3 / make a lava golem: brand new monsters from the AI."""
    count = next((min(int(a), 5) for a in args if a.isdigit()), 1)
    idea = " ".join(a for a in args if not a.isdigit()).strip()
    sync(cfg)
    if not forge.godot_path(cfg) and not cfg.get("make_local"):
        # Without Godot here the result can't be test-built, so GitHub makes it
        # (with free cloud AI and Godot); this device does no AI work at all.
        folder = os.path.join(project(cfg), REQUESTS)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "%d.json" % int(time.time()))
        save_json(path, {"idea": idea, "count": count})
        git(cfg, "add", path)
        git(cfg, "commit", "-q", "-m", "Cinder AI: asked GitHub for %d new monster(s)%s" % (count, (": " + idea) if idea else ""))
        say("Asked GitHub to make %d new monster(s) with free AI." % count)
        say("Saving to GitHub...")
        git(cfg, "push", "-q", "origin", cfg["branch"])
        say("Sent. The new monster and its picture appear in about 15 minutes. Type: look")
        return
    ai, made = brain(cfg), 0
    for _ in range(count):
        try:
            make_here(cfg, ai, idea)
            made += 1
        except (forge.ForgeError, ValueError) as error:
            say("Problem: %s" % error)
    if made:
        publish(cfg)


def cmd_team(cfg, args):
    crew = team(cfg)
    if not crew:
        say("No team set. Put \"team\": \"A\", \"B\" or \"C\" in ~/.cinder/config.json (see teams.json).")
        return
    say("%s on %s" % (crew["name"], crew["device"]))
    say("Job: " + crew["job"])
    say("Size: %s. Works every %s hours: %s." % (crew["grid"], crew["every_hours"], ", ".join(crew["rounds"])))
    say("Free AI, first choice: %s (%s)" % (crew["providers"][0], crew["models"][0]))


def cmd_auto(cfg, args):
    """Runs forever: every few hours the team does its job (see teams.json)."""
    INTERACTIVE[0] = False
    while True:
        cfg = config()
        crew = team(cfg)
        if not crew:
            say("auto needs a team; type: team")
            return
        for job in crew.get("rounds", ["make"]):
            say("%s %s: %s" % (time.strftime("%Y-%m-%d %H:%M"), crew["name"], job))
            run(cfg, job, [])
        time.sleep(float(crew.get("every_hours", 4)) * 3600)


def cmd_requests(cfg, args):
    """GitHub Actions: makes every queued monster request, commits, no push."""
    folder = os.path.join(project(cfg), REQUESTS)
    pending = sorted(f for f in os.listdir(folder) if f.endswith(".json")) if os.path.isdir(folder) else []
    if not pending and "--scheduled" in args:
        pending = [None]  # the daily run: one new monster of the AI's own choosing
    ai = brain(cfg)
    for file in pending:
        job = load_json(os.path.join(folder, file), {}) if file else {}
        made = 0
        for _ in range(min(int(job.get("count", 1)), 5)):
            try:
                make_here(cfg, ai, job.get("idea", ""))
                made += 1
            except (forge.ForgeError, ValueError) as error:
                say("Problem: %s" % error)
        if file and made:  # kept when nothing worked, so the next run tries again
            git(cfg, "rm", "-q", os.path.join(project(cfg), REQUESTS, file))
            git(cfg, "commit", "-q", "-m", "Cinder AI: finished request %s" % file)


def cmd_look(cfg, args):
    url = "https://github.com/%s/tree/%s/Projects/Cinder/previews" % (cfg["github"], cfg["branch"])
    raw = "https://raw.githubusercontent.com/%s/%s/Projects/Cinder/previews/" % (cfg["github"], cfg["branch"])
    if not INTERACTIVE[0]:
        say("![All models](%s_lineup.png?t=%d)" % (raw, int(time.time())))
        say("All pictures: " + url)
        return
    say(url)
    if shutil.which("termux-open-url"):
        subprocess.run(["termux-open-url", url])


def cmd_undo(cfg, args):
    sync(cfg)
    last = git(cfg, "log", "-1", "--format=%H %s")
    if "Cinder AI:" not in last and "Phone AI:" not in last:
        say("The last change was not made by the Cinder AI, so nothing was undone.")
        return
    git(cfg, "revert", "--no-edit", last.split()[0])
    say("Undid: " + last.split(" ", 1)[1])
    publish(cfg)


def cmd_status(cfg, args):
    say(git(cfg, "log", "-8", "--format=%cr  %s", "--", "Projects/Cinder/assets/tuning", check=False) or "No AI changes yet.")
    say("AI is " + ("running" if ai_running(cfg) else "stopped"))
    free = free_memory_mb()
    if free is not None:
        say("Phone memory free: %d MB" % free)


def cmd_stop(cfg, args):
    if cfg["manage_ai"] and shutil.which("pkill"):
        subprocess.run(["pkill", "-f", "ollama"], capture_output=True)
    else:
        for model in (cfg["model"], cfg["small_model"]):
            try:
                body = json.dumps({"model": model, "keep_alive": 0}).encode()
                urllib.request.urlopen(urllib.request.Request(
                    cfg["ai_url"] + "/api/generate", data=body, headers={"Content-Type": "application/json"}), timeout=20)
            except (urllib.error.URLError, OSError):
                pass
    say("AI stopped. Memory is free again.")


HELP = """Commands:
make - the AI invents a brand new monster and builds it
make 3 - three new monsters
make a lava golem with chains - a new monster from your idea
team - what this device's team does
push - the AI writes a plan, improves the next model and saves it
push 5 - do that 5 times
improve hound - plan and improve one model you name
ask make the hound glow more - make a change you describe
look - see the newest pictures
undo - take back the last change
status - recent changes
stop - unload the AI to free memory"""


def cmd_help(cfg, args):
    say(HELP)


COMMANDS = {"help": cmd_help, "make": cmd_make, "monster": cmd_make, "make-requests": cmd_requests, "team": cmd_team, "auto": cmd_auto, "push": cmd_push, "improve": cmd_push, "ask": cmd_ask, "look": cmd_look, "undo": cmd_undo,
            "status": cmd_status, "stop": cmd_stop}


def cmd_menu(cfg, args):
    buttons = [("make a new monster", "make", []), ("push (improve the next model)", "push", []), ("push 5 times", "push", ["5"]),
               ("ask for a change", "ask", []), ("look at the pictures", "look", []),
               ("undo the last change", "undo", []), ("status", "status", []), ("stop the AI", "stop", [])]
    while True:
        say("\n== CINDER ==")
        for i, (label, _, _) in enumerate(buttons, 1):
            say("  %d  %s" % (i, label))
        say("  0  exit")
        choice = input("Press a number: ").strip()
        if choice in ("0", "", "q"):
            return
        if choice.isdigit() and 1 <= int(choice) <= len(buttons):
            _, name, extra = buttons[int(choice) - 1]
            run(cfg, name, extra)


LOCK_PATH = os.path.join(HOME, ".cinder", "busy.lock")


def take_lock():
    """One job at a time per device (the timer and Odysseus chat share a repo)."""
    try:
        if time.time() - os.path.getmtime(LOCK_PATH) > 2 * 3600:  # left over from a crash
            os.remove(LOCK_PATH)
    except OSError:
        pass
    try:
        os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
        os.close(os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        return True
    except FileExistsError:
        return False


def run(cfg, name, args):
    quick = name in ("help", "look", "status", "team", "auto", "menu")
    # Only the background timer waits for the lock; chat and terminal answer right away.
    background = not INTERACTIVE[0] and SINK[-1] is SINK[0]
    if not quick:
        tries = 60 if background else 1
        while not take_lock():
            tries -= 1
            if tries <= 0:
                say("The team is busy with another job right now. Try again in a few minutes.")
                return
            time.sleep(60)
    try:
        (cmd_menu if name == "menu" else COMMANDS[name])(cfg, args)
    except KeyboardInterrupt:
        say("\nStopped.")
    except Exception as error:  # plain words for a non-programmer
        say("Problem: %s" % error)
        say("Nothing was broken. Try again, or type: stop")
    finally:
        if not quick:
            try:
                os.remove(LOCK_PATH)
            except OSError:
                pass


# ---------------------------------------------------------------- Odysseus

def serve(cfg):
    """Pretend to be an OpenAI-style model called "cinder" on 127.0.0.1, so
    Odysseus (or any chat app) can run the commands by typing them."""
    import http.server
    import threading

    lock = threading.Lock()
    INTERACTIVE[0] = False

    def user_text(body):
        for message in reversed(body.get("messages", [])):
            if message.get("role") == "user":
                content = message.get("content", "")
                if isinstance(content, list):
                    content = " ".join(part.get("text", "") for part in content if isinstance(part, dict))
                return str(content)
        return ""

    def command_for(text):
        words = re.sub(r"[^\w\s#.]", " ", text.lower()).split()
        if words and words[0] == "auto":
            return "team", []  # the timer runs by itself in the background, never inside a chat
        if words and words[0] in COMMANDS:
            return words[0], words[1:]
        return "help", []

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def send_json(self, obj):
            data = json.dumps(obj).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path.rstrip("/").endswith("/models"):
                self.send_json({"object": "list", "data": [{"id": "cinder", "object": "model", "owned_by": "cinder"}]})
            else:
                self.send_json({"status": "ok", "commands": sorted(COMMANDS)})

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                body = {}
            name, args = command_for(user_text(body))
            stream = bool(body.get("stream"))
            stamp = int(time.time())
            chunk = {"id": "cinder-%d" % stamp, "created": stamp, "model": "cinder"}
            lines = []

            if stream:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()

            def emit(text):
                lines.append(text)
                if stream:
                    delta = {"role": "assistant", "content": text + "\n"} if len(lines) == 1 else {"content": text + "\n"}
                    event = dict(chunk, object="chat.completion.chunk",
                                 choices=[{"index": 0, "delta": delta, "finish_reason": None}])
                    self.wfile.write(("data: " + json.dumps(event) + "\n\n").encode())
                    self.wfile.flush()

            if lock.acquire(blocking=False):
                SINK.append(emit)
                try:
                    run(config(), name, args)
                finally:
                    SINK.pop()
                    lock.release()
            else:
                emit("Busy with the last command. Try again in a minute.")

            if stream:
                done = dict(chunk, object="chat.completion.chunk",
                            choices=[{"index": 0, "delta": {}, "finish_reason": "stop"}])
                self.wfile.write(("data: " + json.dumps(done) + "\n\ndata: [DONE]\n\n").encode())
                self.wfile.flush()
                self.close_connection = True
            else:
                self.send_json(dict(chunk, object="chat.completion", choices=[{
                    "index": 0, "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "\n".join(lines)}}],
                    usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}))

    port = int(cfg["port"])
    print("Cinder is ready for Odysseus at http://127.0.0.1:%d/v1  (model name: cinder)" % port, flush=True)
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def main():
    args = sys.argv[1:]
    name = os.path.basename(sys.argv[0]).replace(".py", "")
    if name not in COMMANDS and name != "menu":
        name = args.pop(0) if args else "menu"
    if name == "serve":
        serve(config())
        return
    if name not in COMMANDS and name != "menu":
        say(__doc__)
        return
    run(config(), name, args)


if __name__ == "__main__":
    main()
