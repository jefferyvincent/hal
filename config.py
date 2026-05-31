"""Configuration, environment bootstrap, and shared constants.

IMPORTANT — import order: importing this module performs environment bootstrap
that MUST run before torch / torchcodec / Piper / faster-whisper are imported:
  1. COQUI_TOS_AGREED
  2. registering the FFmpeg shared-DLL directory (Windows DLL resolution)
  3. forcing UTF-8 on stdout/stderr
  4. loading .env
server.py therefore imports config FIRST, before any heavy third-party import.
"""
import os

os.environ["COQUI_TOS_AGREED"] = "1"

# torchcodec (required by TTS as of recent versions) loads the FFmpeg shared
# libraries via Windows DLL resolution. Python 3.8+ no longer searches PATH
# for DLLs — we need to register the directory explicitly. Installed by
# `winget install Gyan.FFmpeg.Shared` (8.1.1 full-shared build).
_FFMPEG_DLL_DIR = r"C:\Users\Gamer\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Shared_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build-shared\bin"
if os.path.isdir(_FFMPEG_DLL_DIR):
    os.add_dll_directory(_FFMPEG_DLL_DIR)

import sys

# Force UTF-8 on stdout/stderr. We launch with output redirected to log files,
# which makes Python fall back to Windows cp1252 — that throws UnicodeEncodeError
# and crashes the turn whenever a reply contains a character like → or a curly
# quote. errors="replace" keeps logging non-fatal even for stray glyphs.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path

import torch

# --- Configuration ----------------------------------------------------------
# Minimal .env loader (no python-dotenv dependency).
_ENV_PATH = Path("./.env")
if _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip())

MASSIVE_API_KEY = os.environ.get("MASSIVE_API_KEY", "")
MASSIVE_BASE_URL = "https://api.massive.com"

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen3.6:27b"  # default LLM (smart, slower)
OLLAMA_FAST_MODEL = "llama3.2:3b"  # used when client asks for fast model
OLLAMA_VISION_MODEL = "qwen2.5vl:7b"  # default vision model (accurate)
OLLAMA_VISION_FAST_MODEL = "qwen2.5vl:3b"  # used when client asks for "fast" mode
HAL_REFERENCE_WAV = "static/hal_reference.bak.wav"
# Built-in XTTS v2 studio speaker. Set to a name (e.g. "Damien Black",
# "Royston Min", "Aaron Dreschner", "Viktor Eka") to use a pre-trained voice
# with zero cloning artifacts. Set to None to fall back to cloning from
# HAL_REFERENCE_WAV. Damien Black = cool, neutral, slightly deep — HAL-ish.
HAL_SPEAKER = "Damien Black"
# Piper TTS voice — fast CPU synthesis (~4x realtime), no GPU/VRAM needed.
# Pulled via: python -m piper.download_voices <name> --download-dir <dir>
PIPER_VOICE_PATH = "D:/hal_scratch/piper_voices/en_US-ryan-medium.onnx"
# Negative semitones = deeper voice. -2 is a noticeable drop, -4 is gravelly.
# Set to 0 to disable pitch shift entirely. The torchaudio implementation runs
# on CPU (separate from XTTS on GPU) and adds noticeable per-sentence latency,
# which contributes to gaps in streamed playback. Disabled by default until we
# move to a cleaner algorithm (librosa/rubberband) or do it on GPU.
TTS_PITCH_SHIFT_STEPS = 0
WHISPER_MODEL_SIZE = "medium"
WHISPER_PROMPT = (
    "Conversation with HAL 9000, the AI computer from 2001: A Space Odyssey. "
    "User is Jeffery. Topics include PowerShell, Python, Ollama, files, and tasks "
    "on a Windows desktop."
)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

SCRATCH_DIR = Path("D:/hal_scratch").resolve()
SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = Path("./hal_history.json").resolve()  # legacy single-history file
CONVERSATIONS_DIR = Path("D:/hal_scratch/conversations").resolve()
CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path("D:/hal_scratch/hal.db").resolve()
MAX_HISTORY_MESSAGES = 40
MAX_TITLE_CHARS = 60

MAX_TOOL_OUTPUT_CHARS = 4000
MAX_AGENT_ITERATIONS = 12
MAX_ATTACHMENT_TEXT_CHARS = 100_000  # per text attachment
MAX_ATTACHMENT_COUNT = 50

# When True, HAL runs every proposed command without console y/N approval.
# Telemetry still records each call so you can audit. Flip to False to
# require manual approval at the server console again.
AUTO_APPROVE_TOOLS = True
