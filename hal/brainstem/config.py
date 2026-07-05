"""Configuration, environment bootstrap, and shared constants.

IMPORTANT — import order: importing this module performs environment bootstrap
that MUST run before torch / torchcodec / Piper / faster-whisper are imported:
  1. COQUI_TOS_AGREED
  2. loading .env (so every step + constant below can be configured by it)
  3. forcing UTF-8 on stdout/stderr
server.py therefore imports config FIRST, before any heavy third-party import.
"""
import os
import secrets
from pathlib import Path

os.environ["COQUI_TOS_AGREED"] = "1"

# --- Load .env early so every bootstrap step + constant below can read it. ----
# Minimal loader (no python-dotenv dependency). setdefault() means a real shell
# env var always wins over the file.
_ENV_PATH = Path("./.env")
if _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _v = _line.split("=", 1)
        _v = _v.strip()
        # Accept `KEY=value  # note` and `KEY="value"` / `KEY='value'`.
        if _v[:1] in ("'", '"'):
            _end = _v.find(_v[0], 1)
            if _end != -1:
                _v = _v[1:_end]
        else:
            _c = _v.find(" #")  # inline comment must be whitespace-separated
            if _c != -1:
                _v = _v[:_c].rstrip()
        os.environ.setdefault(_k.strip(), _v)

import sys

# Force UTF-8 on stdout/stderr. We launch with output redirected to log files,
# so without a UTF-8 locale Python can fall back to ASCII — that throws
# UnicodeEncodeError and crashes the turn whenever a reply contains a character
# like → or a curly quote. errors="replace" keeps logging non-fatal even for
# stray glyphs.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import torch


# --- Typed .env helpers ---------------------------------------------------
def _env_str(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    return int(os.environ.get(key, str(default)))


def _env_path(key: str, default) -> Path:
    """Resolve an env var to an expanded, absolute Path (default may be str/Path)."""
    return Path(os.environ.get(key, str(default))).expanduser().resolve()


# --- Identity (configurable via .env; defaults preserve current behavior) --
USER_NAME = _env_str("HAL_USER_NAME", "User")
HAL_NAME = _env_str("HAL_NAME", "HAL")
HAL_VERSION = _env_str("HAL_VERSION", "9000")
HAL_CREATOR = _env_str("HAL_CREATOR", "Jeffery Vincent")  # who built HAL
HAL_DESIGNATION = f"{HAL_NAME} {HAL_VERSION}".strip()  # e.g. "HAL 9000"

# --- Scratch root: HAL's derived, fully-rebuildable data (RAG index, SQLite, --
# saved conversations, downloaded TTS voices). Everything below defaults under
# it; override the root once via HAL_SCRATCH_DIR, or any single path on its own.
SCRATCH_DIR = _env_path("HAL_SCRATCH_DIR", Path.home() / "hal_scratch")

# --- Obsidian vault (journal / rules / theses / watchlist) ------------------
# The vault is the human-authored corpus; HAL reads rules from it at boot and
# injects them into the system prompt (restart to pick up edits, for now).
VAULT_ROOT = Path(_env_str("HAL_VAULT", str(Path.home() / "HAL-Vault"))).expanduser()
_RULES_FILE = VAULT_ROOT / "Rules" / "trading-rules.md"
try:
    TRADING_RULES = _RULES_FILE.read_text(encoding="utf-8") if _RULES_FILE.is_file() else ""
except OSError:
    TRADING_RULES = ""  # a missing/unreadable vault must never block boot

MASSIVE_API_KEY = os.environ.get("MASSIVE_API_KEY", "")
MASSIVE_BASE_URL = "https://api.massive.com"

# --- Alpaca brokerage (order execution) -------------------------------------
# HAL places orders through Alpaca via the official alpaca-py SDK. ALPACA_PAPER
# decides paper vs live: true (default) routes every order to the paper account
# so nothing can touch real money until it's deliberately set false. The SDK
# selects the right API host from that flag. ALPACA_AUTOPILOT flips the order
# gate — false (default) stages each order for an explicit confirm; true submits
# immediately once the vault rules gate passes. Both are runtime-togglable.
ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY", "")
ALPACA_PAPER = os.environ.get("ALPACA_PAPER", "true").lower() != "false"
ALPACA_AUTOPILOT = os.environ.get("ALPACA_AUTOPILOT", "false").lower() == "true"

# --- Pre-trade risk engine (portfolio circuit breakers; see sensory.risk) ----
# These cap the whole account over time, independent of any single trade's
# merits — the runaway guard for autopilot. Each can be disabled by setting it
# to 0. Daily-loss latches the kill switch (block new entries until reset).
RISK_MAX_ORDERS_PER_MIN = _env_int("RISK_MAX_ORDERS_PER_MIN", 6)
RISK_MAX_OPEN_POSITIONS = _env_int("RISK_MAX_OPEN_POSITIONS", 20)
RISK_MAX_GROSS_EXPOSURE_PCT = float(os.environ.get("RISK_MAX_GROSS_EXPOSURE_PCT", "200"))
RISK_DAILY_LOSS_LIMIT_PCT = float(os.environ.get("RISK_DAILY_LOSS_LIMIT_PCT", "10"))

# Scalper (autonomous profit-target auto-trader). Only the mandate — capital,
# profit target, loss floor — is set per session; these are the engine defaults.
# Poll is a FLOOR on cadence: the real pace is committee throughput (minutes).
SCALPER_POLL_SECONDS = float(os.environ.get("SCALPER_POLL_SECONDS", "60"))
SCALPER_MAX_CONCURRENT = _env_int("SCALPER_MAX_CONCURRENT", 3)
SCALPER_SCORE_THRESHOLD = _env_int("SCALPER_SCORE_THRESHOLD", 50)  # "moderate" band: enter on solid directional setups, not just "strong" (70)
SCALPER_CATASTROPHIC_STOP_PCT = float(os.environ.get("SCALPER_CATASTROPHIC_STOP_PCT", "15"))

# News watch monitor: poll interval (seconds) and primary RSS source
# ("yahoo" or "google"). Both feeds are keyless; Yahoo is per-symbol headlines.
NEWS_POLL_SECONDS = float(os.environ.get("NEWS_POLL_SECONDS", "300"))
NEWS_PRIMARY_FEED = os.environ.get("NEWS_PRIMARY_FEED", "yahoo")

# Pre-earnings IV-crush screener: how often to scan the watchlist (seconds) and
# how many calendar days ahead an earnings report must fall to be in scope.
# Backs the "skip earnings" rule — flags watchlist names that report soon AND
# carry rich option premium (IV well above recent realized vol), so they can be
# avoided/faded before the post-report IV crush. The earnings calendar comes
# from Nasdaq's keyless endpoint (same no-key spirit as the news feeds); IV
# richness reuses analysis.iv_context. Hourly default — dates and IV regime move
# slowly relative to a 5-minute news poll, and each scan runs live IV pulls.
EARNINGS_POLL_SECONDS = float(os.environ.get("EARNINGS_POLL_SECONDS", "3600"))
EARNINGS_LOOKAHEAD_DAYS = _env_int("EARNINGS_LOOKAHEAD_DAYS", 3)

# Chart bar source: "yahoo" (free, keyless, near-real-time for US equities) or
# "massive" (REST aggregates; freshness depends on the stock-data entitlement).
CHART_DATA_SOURCE = os.environ.get("CHART_DATA_SOURCE", "yahoo")

# Reddit social-sentiment (optional). Reddit blocks keyless JSON, so HAL uses
# app-only OAuth: register a free "script" app at reddit.com/prefs/apps and put
# its client id + secret here. Left blank, the Reddit read stays inert (neutral).
REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", "")

# --- Ollama endpoint + model selection --------------------------------------
# These pick *which* models HAL asks for; where the daemon stores the blobs is
# set on the Ollama service itself via OLLAMA_MODELS (see setup.sh / .env).
OLLAMA_URL = _env_str("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = _env_str("OLLAMA_MODEL", "qwen3.6:27b")  # default LLM (smart, slower)
OLLAMA_FAST_MODEL = _env_str("OLLAMA_FAST_MODEL", "llama3.2:3b")  # when client asks for fast
OLLAMA_VISION_MODEL = _env_str("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")  # default vision (accurate)
OLLAMA_VISION_FAST_MODEL = _env_str("OLLAMA_VISION_FAST_MODEL", "qwen2.5vl:3b")  # vision "fast"

# --- Voice (TTS / STT) ------------------------------------------------------
HAL_REFERENCE_WAV = _env_str("HAL_REFERENCE_WAV", "static/hal_reference.bak.wav")
# Built-in XTTS v2 studio speaker. Set to a name (e.g. "Damien Black",
# "Royston Min", "Aaron Dreschner", "Viktor Eka") to use a pre-trained voice
# with zero cloning artifacts. Set to None to fall back to cloning from
# HAL_REFERENCE_WAV. Damien Black = cool, neutral, slightly deep — HAL-ish.
HAL_SPEAKER = _env_str("HAL_SPEAKER", "Damien Black")
# Piper TTS voice — fast CPU synthesis (~4x realtime), no GPU/VRAM needed.
# Pulled via: python -m piper.download_voices <name> --download-dir <dir>
PIPER_VOICE_PATH = _env_str(
    "HAL_PIPER_VOICE_PATH", str(SCRATCH_DIR / "piper_voices" / "en_US-ryan-medium.onnx")
)
# Negative semitones = deeper voice. -2 is a noticeable drop, -4 is gravelly.
# Set to 0 to disable pitch shift entirely. The torchaudio implementation runs
# on CPU (separate from XTTS on GPU) and adds noticeable per-sentence latency,
# which contributes to gaps in streamed playback. Disabled by default until we
# move to a cleaner algorithm (librosa/rubberband) or do it on GPU.
TTS_PITCH_SHIFT_STEPS = _env_int("TTS_PITCH_SHIFT_STEPS", 0)
WHISPER_MODEL_SIZE = _env_str("WHISPER_MODEL_SIZE", "medium")
WHISPER_PROMPT = (
    f"Conversation with {HAL_DESIGNATION}, the AI computer from 2001: A Space Odyssey. "
    f"User is {USER_NAME}. Topics include bash, Python, Ollama, files, and tasks "
    "on a Linux desktop."
)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# --- Paths (default under SCRATCH_DIR; each independently overridable) -------
# HAL-Vault: the Obsidian vault that doubles as the RAG corpus, HAL write target,
# and live Dataview dashboard source. Override via HAL_VAULT_DIR.
VAULT_DIR = _env_path("HAL_VAULT_DIR", Path.home() / "HAL-Vault")

# LanceDB index and SQLite for RAG live outside the vault so Obsidian doesn't
# try to index them. They're derived data, fully rebuildable from the vault.
RAG_DB_DIR = _env_path("HAL_RAG_DB_DIR", SCRATCH_DIR / "rag")

HISTORY_FILE = Path("./hal_history.json").resolve()  # legacy single-history file
CONVERSATIONS_DIR = _env_path("HAL_CONVERSATIONS_DIR", SCRATCH_DIR / "conversations")
DB_PATH = _env_path("HAL_DB_PATH", SCRATCH_DIR / "hal.db")

RAG_DB_DIR.mkdir(parents=True, exist_ok=True)
SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)

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

# --- LAN access auth --------------------------------------------------------
# Network clients must log in only when HAL_PASSWORD is non-empty; loopback
# (this machine: Tauri app, localhost browser) is always exempt. The login
# cookie is HMAC-signed with HAL_SECRET_KEY — set a stable key in .env so
# sessions survive restarts (otherwise a fresh random key is used each boot).
HAL_PASSWORD = _env_str("HAL_PASSWORD", "")
HAL_SECRET_KEY = _env_str("HAL_SECRET_KEY", "") or secrets.token_hex(32)
