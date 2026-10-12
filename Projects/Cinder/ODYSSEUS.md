# Cinder in Odysseus: easy commands

You type simple commands in your normal Odysseus chat, in the browser or on your phone, and your own AI PC keeps
improving the Cinderdeep voxel models. Claude isn't needed for this.

## Setup (one time, on the AI PC)

1. Press **Win + R**, type `powershell`, and press **Enter**.
2. Paste this line and press **Enter**:
   ```
   irm https://raw.githubusercontent.com/sidesalt/Game-Dev-Resources/ccr-031f1132-nxzsb1/Projects/Cinder/tools/odysseus/install-cinder.ps1 | iex
   ```
   If a GitHub sign-in window opens, sign in. Cinder needs that to save changes.
3. In **Odysseus settings**, where your **Bitez fleet** endpoint is listed, add a new endpoint:
   - **Name:** `Cinder`
   - **URL:** `http://127.0.0.1:8740/v1`
   - **API key:** `cinder` (any text works)
4. Start a chat, pick the model **cinder**, and type `help`.

✅ **It worked if** typing `help` in that chat lists the commands below.

## The commands (type them in the Odysseus chat)

| Type | What happens |
|---|---|
| `make` | The AI invents a brand new monster, builds it in voxels and saves it. |
| `make 3` | Three new monsters. |
| `make a lava golem with chains` | A new monster from your idea. |
| `push` | Improves the next model a little and saves it to GitHub. |
| `push 5` | Does that 5 times in a row. |
| `ask make the hound glow more` | Makes the change you describe. Say the model's name. |
| `look` | Shows the newest picture of all the models. |
| `undo` | Takes back the last change. |
| `status` | Shows the recent changes. |
| `stop` | Unloads the AI so the PC's graphics memory is free again. |
| `help` | Shows this list. |

Anything else you type just shows the list again, so Cinder never guesses what you meant.

## New monsters, made automatically for $0

- **`make` costs nothing and needs no keys.** GitHub makes the monster using OVHcloud's free AI tier
  (no account needed), so your PC and phone do no AI work at all. The pictures appear in about 15 minutes.
- **Every monster is checked before it's kept.** The recipe must pass safety rules, so it can only build voxels,
  and must use the real voxel tools. Godot must also really build it. Problems go back to the AI to fix, up to 4
  times. A final "polish" pass adds detail and is only kept if it still works.
- **Daily new monster:** GitHub also makes one by itself every day, once this branch is merged into `main`.
- **The AI is coached** by `docs/VOXEL_ASSET_GUIDE.md`. Edit it to teach it your taste.
- **Only free models are used.** If OVHcloud is busy or down, Cinder tries the free models below,
  if you've added a key. Paid models are never used.

## Free cloud models in Odysseus (optional)

Both work in Odysseus the same way Cinder does. In **Odysseus settings**, add an endpoint:

| Name | URL | API key |
|---|---|---|
| OpenRouter (pick models ending in `:free`) | `https://openrouter.ai/api/v1` | free key from openrouter.ai/keys |
| OVHcloud (free, no account) | `https://oai.endpoints.kepler.ai.cloud.ovh.net/v1` | leave empty (a made-up key is refused) |

**Ollama Cloud:** in PowerShell on the PC, type `ollama signin`, then `ollama pull gpt-oss:120b-cloud`. It then shows
up in Odysseus next to your local models. The free list changes often, and `gemma4:31b-cloud` is another option.

To let `make` use OpenRouter or Ollama Cloud as backups, put the keys in `%USERPROFILE%\.cinder\config.json`
as `"keys": {"OPENROUTER_API_KEY": "...", "OLLAMA_API_KEY": "..."}`. For the GitHub runs, add them as repository
secrets with the same names.

## How it works and why it's safe

- **Cinder is a small program on your PC.** It runs at `127.0.0.1:8740` and starts by itself when you log in. Odysseus
  talks to it like a model called `cinder`.
- **Odysseus on your phone works too.** Odysseus calls Cinder on the PC itself, so the phone needs nothing extra.
- **The thinking is done by your own `qwen3.5:9b` on Ollama** (port 11434). Cinder never changes Ollama, Bitez,
  Odysseus, the firewall or any security settings.
- **The AI can only change the safe look settings** in `assets/tuning/<model>.json`: size, glow, brightness, tint,
  colour strength, wear and variation. Each one has a safe limit, and unusable answers are thrown away.
- **GitHub rebuilds the 3D models and pictures automatically** about 5 minutes after each `push`.
- **Settings file:** `%USERPROFILE%\.cinder\config.json`. A backup is made whenever setup runs again. To use a
  different AI model, change `"model"` there.
- **To turn it off:** delete **Cinder for Odysseus** from your Startup folder (Win + R, type `shell:startup`).
