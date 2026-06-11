#!/usr/bin/env bash
#
# HAL 9000 — one-shot Linux installer.
#
# Sets up everything server.py needs (Python ML env on GPU) plus the Tauri/React
# frontend toolchain and Ollama. Idempotent: safe to re-run.
#
# Run this from a REAL host terminal (not the VSCode Flatpak terminal), because
# the Node/Ollama steps need apt + sudo and the GPU driver lives on the host.
#
#   ./setup.sh
#
set -euo pipefail
cd "$(dirname "$0")"

# --- Pinned versions (keep torch in sync with requirements.windows.txt) --------
TORCH_VER="2.6.0"
TORCHAUDIO_VER="2.6.0"
CUDA_INDEX="https://download.pytorch.org/whl/cu124"

# Where Ollama keeps its model blobs (~30 GB). Precedence:
#   1. OLLAMA_MODELS already exported in the shell
#   2. the OLLAMA_MODELS= line in .env (single source of truth with HAL)
#   3. the big data drive, so models stay off the system disk
# We parse the one line rather than `source` .env (which holds secrets + would
# execute arbitrary content).
_env_models="$(sed -n 's/^OLLAMA_MODELS=//p' .env 2>/dev/null | tail -1 | tr -d '"'"'"'"')"
OLLAMA_MODELS="${OLLAMA_MODELS:-${_env_models:-/media/jefferyvincent/New Volume1/ollama-models}}"

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m!  %s\033[0m\n' "$*"; }

# True if we can run sudo without blocking on a password prompt (passwordless
# cache, or an interactive terminal where the user can type it). When false we
# skip the system-package steps and tell the user to re-run in a host terminal.
can_sudo() { [ -t 0 ] || sudo -n true 2>/dev/null; }

# --- 0. Sanity: don't run inside the Flatpak sandbox --------------------------
if [ -f /.flatpak-info ]; then
  warn "You're inside a Flatpak sandbox (no apt/sudo, GPU not visible)."
  warn "Open a normal host terminal and run ./setup.sh there instead."
  exit 1
fi

# --- 1. Pick a Python (prefer 3.12/3.11; the ML pins are flaky on 3.13) --------
PY=""
for v in python3.12 python3.11 python3.10 python3; do
  command -v "$v" >/dev/null 2>&1 && { PY="$v"; break; }
done
[ -n "$PY" ] || { warn "No python3 found."; exit 1; }
PYMM="$("$PY" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
say "Using $($PY --version) at $(command -v "$PY")"

# --- 1.5 System prerequisites (apt): venv support + the audio/build libs the --
#         ML stack links against (soundfile->libsndfile, torchcodec/av->ffmpeg).
NEED_APT=()
"$PY" -c 'import ensurepip' 2>/dev/null || NEED_APT+=("python${PYMM}-venv" python3-pip)
command -v ffmpeg >/dev/null 2>&1 || NEED_APT+=(ffmpeg)
command -v gcc    >/dev/null 2>&1 || NEED_APT+=(build-essential)
NEED_APT+=(libsndfile1)  # cheap; apt is a no-op if already present
if [ "${#NEED_APT[@]}" -gt 0 ]; then
  if can_sudo; then
    say "Installing system prerequisites: ${NEED_APT[*]}"
    sudo apt-get update && sudo apt-get install -y "${NEED_APT[@]}"
  else
    warn "Missing system packages and no sudo available here: ${NEED_APT[*]}"
    warn "Run ./setup.sh from a real host terminal (it will prompt for your password)."
    exit 1
  fi
fi

# --- 2. Generate a clean Linux requirements file from the Windows export ------
# UTF-16 -> UTF-8, drop CRLF, strip Windows-only + CUDA-torch lines (torch is
# installed separately from the PyTorch index below).
say "Regenerating requirements.linux.txt from requirements.windows.txt"
iconv -f UTF-16 -t UTF-8 requirements.windows.txt \
  | tr -d '\r' \
  | grep -viE '^(pywin32|torch|torchaudio)==' \
  > requirements.linux.txt

# --- 3. Python venv + GPU torch + the rest -----------------------------------
if [ ! -d .venv ]; then
  say "Creating virtualenv (.venv)"
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip wheel

say "Installing GPU torch ${TORCH_VER} (CUDA 12.4)"
pip install "torch==${TORCH_VER}" "torchaudio==${TORCHAUDIO_VER}" --index-url "$CUDA_INDEX"

say "Installing remaining Python deps"
pip install -r requirements.linux.txt

python - <<'PY'
import torch
print(f"torch {torch.__version__} | CUDA available: {torch.cuda.is_available()} | "
      f"device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only'}")
PY
deactivate

# --- 4. Node (frontend) ------------------------------------------------------
if command -v npm >/dev/null 2>&1; then
  say "Node already present: $(node --version)"
  say "Installing frontend deps (app/)"
  ( cd app && npm install )
elif can_sudo; then
  say "Installing Node.js + npm (sudo)"
  sudo apt-get update && sudo apt-get install -y nodejs npm
  say "Installing frontend deps (app/)"
  ( cd app && npm install )
else
  warn "Skipping Node install: needs sudo. Re-run ./setup.sh in a host terminal."
fi

# --- 5. Ollama (the LLM backend) ---------------------------------------------
if command -v ollama >/dev/null 2>&1; then
  say "Ollama already present: $(ollama --version 2>&1 | head -1)"
elif can_sudo; then
  say "Installing Ollama (via official script)"
  curl -fsSL https://ollama.com/install.sh | sh
else
  warn "Skipping Ollama install: needs sudo. Re-run ./setup.sh in a host terminal."
fi

# --- 5.5 Point Ollama's model store at $OLLAMA_MODELS -------------------------
# Ollama reads OLLAMA_MODELS for where it keeps blobs. The official installer
# runs the daemon as a dedicated 'ollama' user, but our target lives on an NTFS
# drive mounted uid=1000 under /media (which that user can neither own nor
# traverse). So override the service to run as the invoking user, carry the env
# var, and wait for the drive to be mounted before starting.
configure_ollama_models_dir() {
  local dir="$1" user grp
  user="$(id -un)"; grp="$(id -gn)"
  say "Pointing Ollama model store at: $dir (service runs as $user)"
  mkdir -p "$dir"  # we own the NTFS mount (uid=1000), so no chown/sudo needed

  if systemctl list-unit-files 2>/dev/null | grep -q '^ollama\.service'; then
    sudo mkdir -p /etc/systemd/system/ollama.service.d
    sudo tee /etc/systemd/system/ollama.service.d/override.conf >/dev/null <<EOF
[Service]
User=$user
Group=$grp
Environment="OLLAMA_MODELS=$dir"
RequiresMountsFor="$dir"
EOF
    sudo systemctl daemon-reload
    sudo systemctl restart ollama
    warn "Ollama now waits for $dir to mount; it comes up after you log in."
  else
    warn "No ollama systemd service found; exporting OLLAMA_MODELS for this run only."
    export OLLAMA_MODELS="$dir"
  fi
}

if command -v ollama >/dev/null 2>&1; then
  if can_sudo; then
    configure_ollama_models_dir "$OLLAMA_MODELS"
  else
    warn "Skipping model-dir setup (needs sudo). Re-run in a host terminal to apply"
    warn "  OLLAMA_MODELS=$OLLAMA_MODELS"
  fi
fi

# --- 6. Ollama models (heavy: ~30 GB total). Opt in with PULL_MODELS=1 --------
if command -v ollama >/dev/null 2>&1 && [ "${PULL_MODELS:-0}" = "1" ]; then
  say "Pulling Ollama models into $OLLAMA_MODELS (this is large)"
  for m in qwen3.6:27b llama3.2:3b qwen2.5vl:7b qwen2.5vl:3b; do
    ollama pull "$m"
  done
else
  warn "Skipping model pulls. When ready:  PULL_MODELS=1 ./setup.sh   (or pull individually)"
  warn "  Models used: qwen3.6:27b (smart), llama3.2:3b (fast), qwen2.5vl:7b/3b (vision)"
fi

say "Done. Start the server with:  source .venv/bin/activate && python server.py"
say "Frontend (browser mode):       cd app && npm run dev   ->  http://localhost:1420"
