# Cinder teams

Three machines, three separate teams, one game. Each team designs and builds voxel assets by itself on a timer,
with free cloud AI only (no local AI, so every GPU stays free for gaming), and checks every one in Godot before
saving it to GitHub. The plan lives in `teams.json`. Edit it to change a team's job, size, models or timing.

| Team | Machine | Job | Size | Every | First-choice free AI |
|---|---|---|---|---|---|
| **A** | NewBigSalt (DigitalSalt PC) | Bosses and big monsters | 60-96 | 6 h | Ollama Cloud `nemotron-3-ultra` |
| **B** | BigOldSalt (old laptop) | Regular enemies | 30-64 | 4 h | OVHcloud `Qwen3.5-397B` |
| **C** | OldLilSalt (phone) | Small creatures and polishing | 16-40 | 3 h | OVHcloud `gpt-oss-120b` |

**Why separate:** different jobs mean no duplicate monsters. Different first-choice models give each team its own
style and spread the free limits. A lock means each machine runs one job at a time.

**All teams share:** the art guide `docs/VOXEL_ASSET_GUIDE.md`, the safety checks, and the repo.

## Set up a team

- **Windows (Team A or B):** paste into PowerShell, then answer A or B:
  `irm https://raw.githubusercontent.com/sidesalt/Game-Dev-Resources/ccr-031f1132-nxzsb1/Projects/Cinder/tools/odysseus/install-cinder.ps1 | iex`
  It installs Godot, adds the free models to Odysseus, and starts Cinder plus the team timer at every login.
  Sign in to GitHub as **sidesalt** when asked.
- **Phone (Team C):** already set up. The Odysseus On button starts Odysseus, Cinder and the timer.

## In Odysseus

Pick the model **cinder**, then type:
- `team` to see this machine's job
- `make a lava golem` to make one now
- `status` to see recent changes
