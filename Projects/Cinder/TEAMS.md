# Cinder teams

Three machines, three separate teams, one game. Each team designs and builds voxel assets by itself on a timer,
with free cloud AI only (no local AI, so every GPU stays free for gaming), and checks every one in Godot before
saving it to GitHub. The plan lives in `teams.json`. Edit it to change a team's job, size, models or timing.

| Team | Machine | Job | Size | Every | First-choice free AI |
|---|---|---|---|---|---|
| **A** | LnS (new phone) | Regular enemies | 30-64 | 4 h | OVHcloud `Qwen3.5-397B` |
| **B** | BoS (old laptop) | Bosses and big monsters | 60-96 | 6 h | Ollama Cloud `nemotron-3-ultra` |
| **C** | LoS (old phone) | Small creatures and polishing | 16-40 | 3 h | OVHcloud `gpt-oss-120b` |

DigitalSalt (the main PC) is not a team: it stays free for gaming.

**Why separate:** different jobs mean no duplicate monsters. Different first-choice models give each team its own
style and spread the free limits. A lock means each machine runs one job at a time.

**All teams share:** the art guide `docs/VOXEL_ASSET_GUIDE.md`, the safety checks, and the repo.

## Set up a team

- **New phone (LnS, Team A):** install Termux and Termux:Widget from F-Droid, open Termux and paste:
  `curl -fsSL https://raw.githubusercontent.com/sidesalt/Game-Dev-Resources/ccr-031f1132-nxzsb1/Projects/Cinder/tools/phone/install-team.sh | bash -s -- A`
  It asks for your Ollama Cloud key (optional) and a GitHub sign-in (use **sidesalt**). If Odysseus isn't on the new
  phone yet, Cinder still works. To add Odysseus, copy `odysseus-src.tar.gz` and `odysseus-install-ubuntu.sh` from
  the old phone's `/sdcard/GameDev/tools/` to the same folder on the new phone, run
  `proot-distro login ubuntu -- bash /sdcard/GameDev/tools/odysseus-install-ubuntu.sh`, then the line above again.
- **Old laptop (BoS, Team B), Windows:** paste into PowerShell, and press Enter for team B:
  `irm https://raw.githubusercontent.com/sidesalt/Game-Dev-Resources/ccr-031f1132-nxzsb1/Projects/Cinder/tools/odysseus/install-cinder.ps1 | iex`
- **Old phone (LoS, Team C):** already set up. The **Odysseus On** button starts everything.

## In Odysseus

Pick the model **cinder**, then type:
- `team` to see this machine's job
- `make a lava golem` to make one now
- `status` to see recent changes
