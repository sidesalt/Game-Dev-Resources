#!/data/data/com.termux/files/usr/bin/bash
# Cinder phone AI installer for Termux. Run this one line in Termux:
#
#   curl -fsSL https://raw.githubusercontent.com/sidesalt/Game-Dev-Resources/ccr-031f1132-nxzsb1/Projects/Cinder/tools/phone/install.sh | bash
#
# It installs the AI and the easy commands: push, ask, look, undo, status, stop, menu.
# Add  --claude  at the end (after "bash -s --") to also install the Claude command line.
set -e
BRANCH="ccr-031f1132-nxzsb1"
REPO="https://github.com/sidesalt/Game-Dev-Resources.git"
DIR="$HOME/Game-Dev-Resources"
BIN="${PREFIX:-/usr}/bin"
TOOL="$DIR/Projects/Cinder/tools/phone/cinder.py"

step() { printf '\n\033[1;33m== %s ==\033[0m\n' "$1"; }

step "1/6 Installing apps (git, python, AI, GitHub)"
pkg update -y
pkg install -y git python ollama gh termux-api

step "2/6 Getting the Cinder project"
if [ -d "$DIR/.git" ]; then
	git -C "$DIR" remote set-url origin "$REPO"  # follows the repo if it moved
	git -C "$DIR" fetch -q origin "$BRANCH"
	git -C "$DIR" checkout -q "$BRANCH"
	git -C "$DIR" pull -q --rebase origin "$BRANCH"
else
	git clone -q --branch "$BRANCH" --single-branch "$REPO" "$DIR"
fi
git -C "$DIR" config user.name >/dev/null || git -C "$DIR" config user.name "Cinder Phone AI"
git -C "$DIR" config user.email >/dev/null || git -C "$DIR" config user.email "phone-ai@users.noreply.github.com"

step "3/6 Connecting GitHub (so 'push' can save your changes)"
if ! gh auth status >/dev/null 2>&1; then
	echo "A code will appear. Open the link, sign in to GitHub, and type the code."
	gh auth login --hostname github.com --git-protocol https --web
fi
gh auth setup-git

step "4/6 Making the easy commands"
for name in monster push improve ask look undo status stop menu; do
	printf '#!%s/bash\nexec python3 "%s" %s "$@"\n' "$BIN" "$TOOL" "$name" > "$BIN/$name"
	chmod +x "$BIN/$name"
done
mkdir -p "$HOME/.cinder"

step "5/6 Making home-screen buttons (needs the Termux:Widget app)"
mkdir -p "$HOME/.shortcuts"
for name in monster push menu look stop; do
	label="Cinder $(printf '%s' "$name" | sed 's/./\U&/')"
	printf '#!%s/bash\npython3 "%s" %s\necho\nread -p "Done. Press Enter to close." _\n' "$BIN" "$TOOL" "$name" > "$HOME/.shortcuts/$label"
	chmod +x "$HOME/.shortcuts/$label"
done

step "6/6 Downloading the AI brain (about 1 GB, one time)"
export OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_KEEP_ALIVE=30s
(ollama serve >"$HOME/.cinder/ai.log" 2>&1 &)
sleep 4
ollama pull qwen2.5:1.5b
ollama pull qwen2.5:0.5b
pkill -f "ollama serve" || true

if [ "$1" = "--claude" ]; then
	step "Extra: Claude command line"
	pkg install -y nodejs-lts
	npm install -g @anthropic-ai/claude-code
	echo "Type  claude  inside $DIR to use it (needs your Claude login)."
fi

printf '\n\033[1;32mAll set!\033[0m Type one of these:\n'
echo "  push       improve the next model and save it"
echo "  push 5     do it 5 times"
echo "  ask make the hound glow more"
echo "  look       see the pictures"
echo "  undo       take back the last change"
echo "  stop       stop the AI (frees memory)"
echo "  menu       number buttons for everything"
