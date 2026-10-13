#!/bin/bash
# Cinder team watchdog for a phone (runs inside Ubuntu/proot). Keeps Cinder (port 8740), the team timer and,
# if it is installed, Odysseus (port 7100) running, and restarts them within seconds whenever they crash or
# Android kills them. Installed as ~/.cinder/odysseus-watch.sh; stop everything with ~/.cinder/services-stop.sh.
# Logs: ~/.cinder/cinder.log, ~/.cinder/team.log, /sdcard/GameDev/odysseus.log
REPO="${CINDER_REPO_DIR:-/root/Game-Dev-Resources}"
TOOL="$REPO/Projects/Cinder/tools/phone/cinder.py"
# no-npx + REQUIRE_CACHE skip Odysseus's ~170 MB browser tool, which got Termux killed on a 3.6 GB phone.
export PATH=/opt/odysseus/no-npx:/usr/local/bin:/usr/bin:/bin ODYSSEUS_DATA_DIR=/root/odysseus-data AUTH_ENABLED=true \
	LOCALHOST_BYPASS=false LLM_HOST=127.0.0.1 ODYSSEUS_BROWSER_MCP_REQUIRE_CACHE=1 GODOT_SILENCE_ROOT_WARNING=1
mkdir -p "$HOME/.cinder" /sdcard/GameDev 2>/dev/null
echo $$ > "$HOME/.cinder/watch.pid"  # the whole process group; services-stop.sh kills it
keep() { # name, health url, log, command...
	local name="$1" url="$2" log="$3"; shift 3
	while true; do
		if ! curl -s -m 5 -o /dev/null "$url"; then
			echo "$(date '+%F %T') watchdog: starting $name" >> "$log"
			"$@" >> "$log" 2>&1
			echo "$(date '+%F %T') watchdog: $name stopped (exit $?), restarting" >> "$log"
		fi
		sleep 5
	done
}
keep Cinder http://127.0.0.1:8740/v1/models "$HOME/.cinder/cinder.log" python3 "$TOOL" serve &
# The team timer (teams.json): this phone's team does its job every few hours.
( while true; do python3 "$TOOL" auto >> "$HOME/.cinder/team.log" 2>&1; sleep 60; done ) &
if [ -x /opt/odysseus/venv/bin/python ]; then
	cd /opt/odysseus && keep Odysseus http://127.0.0.1:7100/api/health /sdcard/GameDev/odysseus.log \
		venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 7100
else
	wait
fi
