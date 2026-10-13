#!/bin/bash
# Stops the watchdog and everything it runs (Odysseus, Cinder, the team timer): its whole process group.
kill -- -"$(cat "$HOME/.cinder/watch.pid")" 2>/dev/null && echo "Odysseus and Cinder stopped." || echo "Not running."
