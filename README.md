# HAL 9000 — Voice Assistant

Local voice assistant with a HAL 9000 themed UI. Speaks via XTTS, listens via Whisper,
thinks via Ollama. Runs entirely on the host machine — no cloud round-trips.

## Architecture

Two completely decoupled processes:

```
+--------------------+         WebSocket          +-----------------------+
|  Tauri app (UI)    |  <--------------------->   |  server.py (FastAPI)  |
|  React + Vite      |   ws://localhost:8000/ws   |  Ollama / Whisper /   |
|  webview           |                            |  XTTS  — GPU heavy    |
+--------------------+                            +-----------------------+
        |                                                    |
   user keypress / mic                              .venv (fragile torch env)
```

- `server.py` owns all model weights and the conversation history.
- The Tauri app is just a webview. Open the browser at `http://localhost:1420` instead
  and you get the same UI.
- The WS client (`app/src/lib/ws.ts`) reconnects on every user action, so the
  two processes can start in either order.

## Layout

```
hal-voice/
  server.py            FastAPI server, all AI logic
  start-hal.sh         Linux/macOS launcher: activates .venv, runs server.py, logs to hal.log
  start-hal.ps1        Windows launcher (same job, PowerShell)
  static/              Legacy single-file UI (still served as a fallback)
  app/                 Tauri 2 + React + Vite frontend (current UI)
    src/               React components, stores, lib
    src-tauri/         Rust shell (window, tray, global shortcut, autostart)
```

## Setup (Linux)

One command from a **host terminal** (not the VSCode Flatpak terminal — it has no
`sudo`/`apt` and can't see the GPU):

```sh
./setup.sh
```

It installs system prereqs (python venv, ffmpeg, libsndfile), creates `.venv`,
installs GPU torch (CUDA 12.4) + the rest of `requirements.linux.txt`, sets up the
`app/` frontend, and installs Ollama. The Python requirements are regenerated from
`requirements.windows.txt` each run, so the two stay in sync.

Pull the LLM/vision models (~30 GB, separate step):

```sh
PULL_MODELS=1 ./setup.sh        # or: ollama pull qwen3.6:27b  (etc.)
```

## Development

### Server

```bash
./start-hal.sh                                   # launcher: venv + server, logs to hal.log
# or, in an already-activated shell:
source .venv/bin/activate && python server.py
```

Logs stream to `hal.log`. Server listens on `:8000`.

### UI — browser mode (fast iteration)

```bash
cd app
npm install        # first time only
npm run dev
```

Opens at `http://localhost:1420`. Vite proxies `/ws` to FastAPI on `:8000`.

### UI — native Tauri window

```bash
cd app
npm run tauri:dev
```

First run compiles the Rust shell (5–10 min). Subsequent runs are fast.

### Production build

```bash
cd app
npm run tauri:build
```

Produces a bundle in `app/src-tauri/target/release/bundle/` (AppImage + `.deb`
on Linux). Launch it once to register HAL for login autostart (see Auto-start
below).

## Network access (LAN)

`server.py` binds `0.0.0.0:8000`, so HAL is reachable from other devices once
you serve the UI from FastAPI and protect it with a password.

1. **Build the UI.** FastAPI serves `app/dist` when present (else the legacy
   `static/` UI):

   ```bash
   cd app && npm run build
   ```

2. **Set a password** in `.env`. Network devices must then log in; this machine
   (localhost + the Tauri app) is always exempt. Empty `HAL_PASSWORD` disables
   auth.

   ```ini
   HAL_PASSWORD=your-password-here
   HAL_SECRET_KEY=...   # python -c "import secrets; print(secrets.token_hex(32))"
   ```

3. **Connect.** Start the server, then open `http://<host-ip>:8000/` from any
   device on the network (e.g. `http://192.168.1.199:8000/`). A login page
   appears; after the password, the UI and its WebSocket are unlocked.

> **Security:** HAL runs commands with `AUTO_APPROVE_TOOLS = True`, so anyone who
> logs in can execute code on this machine. Use a strong password and only expose
> HAL on a trusted network. If a firewall is active, allow the port:
> `sudo ufw allow 8000/tcp`.

## Auto-start at logon

Two pieces, configured independently.

### 1. Server — systemd user service

Run the server with the launcher, which activates the venv and appends all
output to `hal.log`:

```bash
./start-hal.sh            # foreground
./start-hal.sh &          # or background it
```

To start it at login, add a user service at `~/.config/systemd/user/hal.service`
(replace the path with your checkout):

```ini
[Unit]
Description=HAL Voice Server
After=network.target

[Service]
WorkingDirectory=/path/to/hal
ExecStart=/path/to/hal/start-hal.sh
Restart=on-failure

[Install]
WantedBy=default.target
```

Enable it, and keep it running without an active login session:

```bash
systemctl --user daemon-reload
systemctl --user enable --now hal
loginctl enable-linger "$USER"
```

Check it (give it ~20s for model warmup):

```bash
systemctl --user status hal
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/
tail -f hal.log
```

### 2. App window — Tauri autostart plugin

Code lives in `app/src/App.tsx` and `app/src-tauri/src/lib.rs`. Guarded by
`import.meta.env.PROD` so `npm run tauri:dev` does not pollute startup.

After running `npm run tauri:build` and launching the installed app once, the
plugin registers HAL via an XDG autostart entry in `~/.config/autostart/`. Delete
that `.desktop` file (or remove it from your desktop's Startup Applications) to
disable.

### Startup order caveat

Server and Tauri window fire at roughly the same time. The server takes
10–30s to load Whisper / XTTS / Ollama weights. During that window the UI
will briefly show `ERROR / Connection failed`. Clicking the mic or sending
text once the server is ready triggers a fresh WS connect and recovers.

### Summon / hide from anywhere

`Ctrl+Space` toggles the HAL window — wired in `app/src-tauri/src/lib.rs`
via `tauri-plugin-global-shortcut`. Works even when the window is hidden.

## Features (UI)

- Voice loop: tap mic, speak, VAD detects end-of-utterance, server transcribes
  and replies with streamed TTS audio.
- Text directives via the bottom input bar.
- File attachments: drag-drop anywhere, file picker (`+`), or camera button.
- Camera-attach: one-shot photo snap (Cancel / Flip / Snap), separate from
  immersive live-vision mode.
- Immersive mode (eye icon): full-screen camera / screen share / map / external
  video as backdrop, with a "live cognition" overlay of HAL's tool calls.
- Conversations: switch / delete / new. Opened from the HUD's `CHATS` button.
- Telemetry panel: rolling log of tool calls (right edge, expandable).
- Fast / smart model toggle (lightning bolt).
- Wipe memory (trash icon).
- Stop button (interrupt speech/generation).
- Fullscreen chat mode (hides the eye, expands transcript).

## Known things to know

- **Torch env is fragile.** The `.venv` has a hand-pinned `torch / torchaudio /
  torchcodec / FFmpeg` matrix (see `setup.sh` for the exact CUDA pins). Do not
  blindly `pip upgrade`.
- **VRAM budget.** RTX 3090 (24 GB) is shared between Ollama LLM, Whisper, and
  XTTS. Loading a larger LLM may starve TTS.
- **Map embed has no API key.** `app/src/components/immersive/ImmersiveStage.tsx`
  uses the keyless `maps.google.com/maps?q=...&output=embed` URL. Swap in
  `https://www.google.com/maps/embed/v1/place?key=...&q=...` if Google starts
  rate-limiting you.
- **Two GitHub remotes exist:** the clean `hal` repo (default) and the bloated
  `hal-voice` repo (has secrets in history — do not push to).

## Repo layout reference

Key files when something breaks:

| File | Purpose |
| --- | --- |
| `server.py` | FastAPI WS server, all model invocation |
| `start-hal.sh` | Venv activation + server launch (Linux) |
| `app/src/App.tsx` | Root layout, autostart hook, immersive thought mirroring |
| `app/src/lib/ws.ts` | WS client (binary audio + JSON envelopes) |
| `app/src/lib/audio.ts` | Gap-free WAV chunk playback queue |
| `app/src/lib/vad.ts` | Voice activity detector (end-of-utterance) |
| `app/src/stores/connection.ts` | Mode machine, mic recorder, all WS commands |
| `app/src-tauri/src/lib.rs` | Tauri shell: tray, hotkey, autostart plugin init |
| `app/src-tauri/tauri.conf.json` | Window chrome, bundle config |
| `app/src-tauri/capabilities/default.json` | Tauri permission allowlist |
