#!/usr/bin/env bash
#
# HAL launcher (Linux/macOS) — activate the venv and run server.py, appending
# all output to hal.log. The Linux counterpart of start-hal.ps1.
#
#   ./start-hal.sh            # run in the foreground
#   ./start-hal.sh &          # or background it
#
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  echo "HAL: no virtualenv found at .venv/ — run ./setup.sh first." >&2
  exit 1
fi

ts="$(date '+%Y-%m-%d %H:%M:%S')"
printf '\n=== HAL starting %s ===\n' "$ts" >> hal.log
exec .venv/bin/python -u server.py >> hal.log 2>&1
