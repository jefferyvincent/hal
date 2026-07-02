#!/usr/bin/env bash
#
# HAL launcher (Linux/macOS) — activate the venv and run server.py, appending
# all output to hal.log.
#
#   ./start-hal.sh            # run in the foreground
#   ./start-hal.sh &          # or background it
#
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  echo "HAL: no virtualenv found at .venv/ — run ./setup.sh first." >&2
  exit 1
fi

# --- Preflight: HAL needs Ollama (the LLM) up, which needs its model drive ----
# Parse single .env lines rather than sourcing the file (it holds secrets).
_env_val() { sed -n "s/^$1=//p" .env 2>/dev/null | tail -1 | tr -d '"'\'''; }

# Ollama base URL (scheme://host:port) derived from OLLAMA_URL, minus the path.
OLLAMA_URL="$(_env_val OLLAMA_URL)"; OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434/api/chat}"
OLLAMA_HOST="$(printf '%s' "$OLLAMA_URL" | sed -E 's#(https?://[^/]+).*#\1#')"
ollama_up() { curl -fsS -m 3 "$OLLAMA_HOST/api/tags" >/dev/null 2>&1; }

# --- HTTPS front (Caddy) ------------------------------------------------------
# Caddy (setup.sh installs it to ~/.local/bin) reverse-proxies https://localhost:8443
# to server.py on :8000 using a locally-trusted cert. Where the browser lands is
# set below and printed once HAL is up.
CADDY_BIN="$(command -v caddy 2>/dev/null || true)"; [ -n "$CADDY_BIN" ] || CADDY_BIN="$HOME/.local/bin/caddy"
# Pin Caddy's data dir to the REAL ~/.local/share so the CA it serves is the same
# one `caddy trust` installed — the VSCode Flatpak terminal otherwise redirects
# XDG_DATA_HOME into its sandbox and Caddy would mint a different, untrusted CA.
CADDY_XDG="$HOME/.local/share"
HAL_URL="http://localhost:8000"                    # updated to https:// if Caddy comes up
caddy_up() { curl -skS -m 3 -o /dev/null https://localhost:8443/ 2>/dev/null; }

# Ollama's model store lives on a removable drive; its systemd service waits for
# that mount. If the path is missing, try to mount the drive by its label
# (the directory name under /media/<user>/) via udisksctl (no sudo needed).
ensure_model_drive() {
  local md label dev
  md="$(_env_val OLLAMA_MODELS)"
  [ -n "$md" ] && [ ! -d "$md" ] || return 0
  label="$(printf '%s' "$md" | sed -nE 's#^/media/[^/]+/([^/]+)/.*#\1#p')"
  dev="/dev/disk/by-label/$label"
  if [ -n "$label" ] && [ -e "$dev" ] && command -v udisksctl >/dev/null 2>&1; then
    echo "HAL: mounting model drive '$label'..." >&2
    udisksctl mount -b "$dev" >/dev/null 2>&1 || true
  fi
  [ -d "$md" ] || echo "HAL: model drive missing ($md) — mount it (Files app) or Ollama models won't load." >&2
}

# Start Ollama if it isn't already answering, then wait for it to come up.
ensure_ollama() {
  if ollama_up; then echo "HAL: Ollama already running." >&2; return 0; fi
  echo "HAL: Ollama not responding at $OLLAMA_HOST — starting it..." >&2
  if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl start ollama 2>/dev/null || systemctl --user start ollama 2>/dev/null || true
  elif command -v ollama >/dev/null 2>&1; then
    ollama serve >> hal.log 2>&1 &
  fi
  for _ in $(seq 1 30); do
    ollama_up && { echo "HAL: Ollama is up." >&2; return 0; }
    sleep 1
  done
  echo "HAL: Ollama still unreachable — HAL will start but replies will fail until it's up." >&2
  return 1
}

# Preload the chat model into VRAM in the background. The first request to a big
# model (qwen3.6:27b ~16GB) takes ~minute to load; doing it now — while the
# server loads its own GPU models — means the user's first message is instant.
# keep_alive holds it in memory through the idle gap before they start typing.
warm_ollama() {
  local model
  model="$(_env_val OLLAMA_MODEL)"; model="${model:-qwen3.6:27b}"
  echo "HAL: preloading '$model' (first load is slow; runs in background)..." >&2
  curl -fsS -m 300 "$OLLAMA_HOST/api/chat" \
    -d "{\"model\":\"$model\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"stream\":false,\"keep_alive\":\"30m\"}" \
    >/dev/null 2>&1 &
}

# Bring up the Caddy HTTPS front, if it's installed and a Caddyfile is present.
# Idempotent: if something already answers on 8443 we assume Caddy is up and just
# switch the advertised URL to https. Missing Caddy is non-fatal — HAL still
# serves plain http on :8000.
ensure_caddy() {
  [ -f Caddyfile ] || return 0
  if [ ! -x "$CADDY_BIN" ]; then
    echo "HAL: Caddy not installed — skipping HTTPS (run ./setup.sh). Serving $HAL_URL." >&2
    return 0
  fi
  if caddy_up; then
    HAL_URL="https://localhost:8443"
    echo "HAL: Caddy (HTTPS) already running — $HAL_URL" >&2
    return 0
  fi
  echo "HAL: starting Caddy (HTTPS) on https://localhost:8443 ..." >&2
  if XDG_DATA_HOME="$CADDY_XDG" "$CADDY_BIN" start --config Caddyfile >> hal.log 2>&1; then
    HAL_URL="https://localhost:8443"
    echo "HAL: Caddy up — $HAL_URL" >&2
  else
    echo "HAL: Caddy failed to start (see hal.log) — serving $HAL_URL instead." >&2
  fi
}

# HAL serves the prebuilt React bundle from app/dist. Rebuild it when any source
# under app/ (outside node_modules/dist) is newer than the last build, so UI
# changes show up on launch without a manual `npm run build`. A failed build
# leaves the previous bundle in place rather than blocking startup.
ensure_frontend_build() {
  [ -d app ] && [ -f app/package.json ] || return 0
  if ! command -v npm >/dev/null 2>&1; then
    echo "HAL: npm not found — skipping frontend rebuild (serving existing app/dist)." >&2
    return 0
  fi
  local stale
  if [ ! -f app/dist/index.html ]; then
    stale="yes"
  else
    stale="$(find app -type d \( -name node_modules -o -name dist \) -prune -o \
      -type f -newer app/dist/index.html -print -quit 2>/dev/null)"
  fi
  [ -n "$stale" ] || { echo "HAL: frontend bundle up to date." >&2; return 0; }
  echo "HAL: rebuilding frontend (npm run build)..." >&2
  if ( cd app && npm run build >> ../hal.log 2>&1 ); then
    echo "HAL: frontend rebuilt." >&2
  else
    echo "HAL: frontend build FAILED — see hal.log. Serving previous app/dist." >&2
  fi
}

ensure_model_drive
ensure_frontend_build
ensure_ollama && warm_ollama
ensure_caddy

ts="$(date '+%Y-%m-%d %H:%M:%S')"
printf '\n=== HAL starting %s ===\n' "$ts" >> hal.log

# All server output goes to hal.log, so the terminal would otherwise look dead.
# Tell the user where to watch, and surface a crash instead of swallowing it.
echo "HAL: starting — output goes to hal.log (watch it with:  tail -f hal.log)" >&2
# Remember where this run's log begins so we only inspect its own output, not a
# previous run's (hal.log is append-only and spans many launches).
log_start="$(wc -l < hal.log)"
.venv/bin/python -u server.py >> hal.log 2>&1 &
hal_pid=$!
# Forward Ctrl+C / termination to the server (previously `exec` did this for us).
trap 'kill -INT "$hal_pid" 2>/dev/null' INT TERM

# Loading the GPU models takes a while, so poll (up to ~2 min) until the server
# either prints its ready banner or dies. Either way the user gets a clear
# answer instead of a silent prompt.
this_run() { tail -n +"$((log_start + 1))" hal.log; }
for _ in $(seq 1 120); do
  if ! kill -0 "$hal_pid" 2>/dev/null; then
    echo "HAL: server exited during startup. Last lines of hal.log:" >&2
    this_run | tail -n 20 >&2
    wait "$hal_pid"; exit $?
  fi
  if this_run | grep -q "HAL is running"; then
    echo "HAL: running (pid $hal_pid) — open $HAL_URL" >&2
    break
  fi
  sleep 1
done
wait "$hal_pid"
