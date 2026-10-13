#!/data/data/com.termux/files/usr/bin/bash
# Sets up a phone as a Cinder team, the same way as the old phone (LoS, Team C). Run in Termux:
#
#   curl -fsSL https://raw.githubusercontent.com/sidesalt/Game-Dev-Resources/ccr-031f1132-nxzsb1/Projects/Cinder/tools/phone/install-team.sh | bash -s -- A
#
# The letter is the team (see Projects/Cinder/teams.json): A = LnS (new phone), C = LoS (old phone).
# What it sets up: Ubuntu (proot), the Cinder project, Godot for test-building monsters, Cinder with free cloud AI
# only (no local AI), the team timer, a watchdog that restarts everything when Android kills it, the free cloud
# models in Odysseus (if Odysseus is installed), and the "Odysseus On/Off" home-screen buttons.
set -e
TEAM="$(printf '%s' "${1:-A}" | tr a-z A-Z)"
BRANCH="ccr-031f1132-nxzsb1"
REPO="https://github.com/sidesalt/Game-Dev-Resources.git"
step() { printf '\n\033[1;33m== %s ==\033[0m\n' "$1"; }

step "1/5 Termux apps"
pkg install -y proot-distro tmux curl termux-api >/dev/null
proot-distro list 2>/dev/null | grep -q "ubuntu.*installed" || [ -d "$PREFIX/var/lib/proot-distro/installed-rootfs/ubuntu" ] \
	|| proot-distro install ubuntu

step "2/5 Ubuntu: project, GitHub, Godot, settings (Team $TEAM)"
OLLAMA_KEY=""
if [ -t 0 ] || [ -e /dev/tty ]; then
	read -r -p "Ollama Cloud API key from ollama.com/settings/keys (Enter to skip): " OLLAMA_KEY < /dev/tty || true
fi
proot-distro login ubuntu -- env TEAM="$TEAM" BRANCH="$BRANCH" REPO="$REPO" OLLAMA_KEY="$OLLAMA_KEY" bash -s <<'UBUNTU'
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/dev/null
apt-get install -y -qq git python3 curl unzip gh >/dev/null
DIR=/root/Game-Dev-Resources
if [ -d "$DIR/.git" ]; then
	git -C "$DIR" remote set-url origin "$REPO"
	git -C "$DIR" fetch -q origin "$BRANCH" && git -C "$DIR" checkout -q "$BRANCH"
	git -C "$DIR" pull -q --rebase --autostash origin "$BRANCH"
else
	git clone -q --branch "$BRANCH" --single-branch "$REPO" "$DIR"
fi
git -C "$DIR" config user.name >/dev/null || git -C "$DIR" config user.name "Cinder Team $TEAM"
git -C "$DIR" config user.email >/dev/null || git -C "$DIR" config user.email "cinder-team@users.noreply.github.com"
if ! gh auth status >/dev/null 2>&1; then
	echo "Sign in to GitHub as sidesalt: a code appears, open the link and type it."
	gh auth login --hostname github.com --git-protocol https --web --scopes workflow < /dev/tty
fi
gh auth setup-git

mkdir -p ~/.cinder/godot
G=~/.cinder/godot/Godot_v4.4.1-stable_linux.arm64
if [ ! -x "$G" ]; then
	curl -fsSL -o ~/.cinder/godot/godot.zip \
		https://github.com/godotengine/godot/releases/download/4.4.1-stable/Godot_v4.4.1-stable_linux.arm64.zip
	unzip -qo ~/.cinder/godot/godot.zip -d ~/.cinder/godot && rm ~/.cinder/godot/godot.zip
fi
GODOT_SILENCE_ROOT_WARNING=1 "$G" --headless --path "$DIR/Projects/Cinder" --import >/dev/null 2>&1 || true

python3 - "$TEAM" "$G" "$OLLAMA_KEY" <<'PY'
import json, os, sys
team, godot, key = sys.argv[1:]
path = os.path.expanduser("~/.cinder/config.json")
cfg = json.load(open(path)) if os.path.exists(path) else {}
cfg.update({"team": team, "cloud_only": True, "godot": godot})
if key:
    cfg.setdefault("keys", {})["OLLAMA_API_KEY"] = key
json.dump(cfg, open(path, "w"), indent=1)
os.chmod(path, 0o600)
print("Settings:", {k: v for k, v in cfg.items() if k != "keys"})
PY
cp "$DIR/Projects/Cinder/tools/phone/ubuntu/watch.sh" ~/.cinder/odysseus-watch.sh
cp "$DIR/Projects/Cinder/tools/phone/ubuntu/services-stop.sh" ~/.cinder/services-stop.sh
chmod +x ~/.cinder/*.sh

if [ -x /opt/odysseus/venv/bin/python ]; then
	echo "Adding the free cloud models to Odysseus..."
	KEYARG=""
	KEY=$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.cinder/config.json'))).get('keys',{}).get('OLLAMA_API_KEY',''))")
	cd /opt/odysseus && ODYSSEUS_DATA_DIR=/root/odysseus-data venv/bin/python \
		"$DIR/Projects/Cinder/tools/odysseus/add_free_endpoints.py" ${KEY:+--ollama-key "$KEY"} 2>&1 | grep -v " INFO " || true
else
	echo "NOTE: Odysseus is not installed in Ubuntu yet. Cinder still works; see TEAMS.md to add Odysseus."
fi
python3 "$DIR/Projects/Cinder/tools/phone/cinder.py" team
UBUNTU

step "3/5 Start and stop commands"
mkdir -p ~/bin ~/.shortcuts
cat > ~/bin/odysseus-start <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
# Starts this phone's Odysseus (http://127.0.0.1:7100), Cinder and the team timer, all inside Ubuntu, under a
# watchdog that restarts them whenever they crash. Log: /sdcard/GameDev/odysseus.log   Stop: odysseus-stop
termux-wake-lock 2>/dev/null
if ! tmux has-session -t =odysseus 2>/dev/null; then
  tmux new-session -d -s odysseus "proot-distro login ubuntu -- bash /root/.cinder/odysseus-watch.sh"
fi
URL=http://127.0.0.1:7100
for i in $(seq 1 120); do curl -s -o /dev/null "$URL/api/health" && break; sleep 3; done
if curl -s -o /dev/null "$URL/api/health"; then
  echo "Odysseus is up: $URL"
  am start -a android.intent.action.VIEW -d "$URL/" >/dev/null 2>&1
else
  echo "Cinder and the team timer are running (Odysseus is not installed or did not start)."
fi
EOF
cat > ~/bin/odysseus-stop <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
# Stops this phone's Odysseus, Cinder and the team timer.
tmux kill-session -t odysseus 2>/dev/null && echo "Stopped." || echo "Was not running."
EOF
chmod +x ~/bin/odysseus-start ~/bin/odysseus-stop

step "4/5 Home-screen buttons (needs the Termux:Widget app)"
printf '#!/data/data/com.termux/files/usr/bin/bash\ntermux-toast "Starting Odysseus..."\n~/bin/odysseus-start\n' > ~/.shortcuts/"Odysseus On"
printf '#!/data/data/com.termux/files/usr/bin/bash\ntermux-toast "$(~/bin/odysseus-stop)"\n' > ~/.shortcuts/"Odysseus Off"
chmod +x ~/.shortcuts/*

step "5/5 Starting Team $TEAM"
~/bin/odysseus-start
printf '\n\033[1;32mTeam %s is set up.\033[0m It works by itself every few hours. Tap "Odysseus On" after a restart.\n' "$TEAM"
