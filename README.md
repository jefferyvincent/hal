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
  start-hal.ps1        Activates .venv and runs server.py, logs to hal.log
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

```powershell
.\start-hal.ps1                 # Windows
```
```sh
source .venv/bin/activate && python server.py    # Linux
```

Logs stream to `hal.log`. Server listens on `:8000`.

### UI — browser mode (fast iteration)

```powershell
cd app
npm install        # first time only
npm run dev
```

Opens at `http://localhost:1420`. Vite proxies `/ws` to FastAPI on `:8000`.

### UI — native Tauri window

```powershell
cd app
npm run tauri:dev
```

First run compiles the Rust shell (5–10 min). Subsequent runs are fast.

### Production build

```powershell
cd app
npm run tauri:build
```

Produces an installer in `app/src-tauri/target/release/bundle/`. Install it once
to register HAL with Windows Startup (see Auto-start below).

## Auto-start at logon

Two pieces, configured independently.

### 1. Server — Windows Task Scheduler (already configured)

A scheduled task named `HAL Voice Server` runs `start-hal.ps1` hidden at user
logon, auto-restarts on failure. Set up with:

```powershell
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
  -Argument '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "C:\Users\Gamer\hal-voice\start-hal.ps1"'
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries -StartWhenAvailable `
  -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
  -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
  -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'HAL Voice Server' -Action $action `
  -Trigger $trigger -Settings $settings -Principal $principal -Force
```

Test without rebooting:

```powershell
Start-ScheduledTask -TaskName 'HAL Voice Server'
# wait ~20s for model warmup, then:
Invoke-WebRequest http://localhost:8000/ -UseBasicParsing | Select-Object StatusCode
```

Disable / remove:

```powershell
Disable-ScheduledTask    -TaskName 'HAL Voice Server'
Unregister-ScheduledTask -TaskName 'HAL Voice Server' -Confirm:$false
```

### 2. App window — Tauri autostart plugin

Code lives in `app/src/App.tsx` and `app/src-tauri/src/lib.rs`. Guarded by
`import.meta.env.PROD` so `npm run tauri:dev` does not pollute startup.

After running `npm run tauri:build` and launching the installed app once, HAL
will appear in **Settings → Apps → Startup**. Disable from there.

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

- **Torch env is fragile.** The `.venv` has a hand-pinned `torch 2.12+cu126 /
  torchaudio 2.11 / torchcodec 0.13 / FFmpeg DLL` matrix. Do not blindly
  `pip upgrade`.
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
| `start-hal.ps1` | Venv activation + server launch |
| `app/src/App.tsx` | Root layout, autostart hook, immersive thought mirroring |
| `app/src/lib/ws.ts` | WS client (binary audio + JSON envelopes) |
| `app/src/lib/audio.ts` | Gap-free WAV chunk playback queue |
| `app/src/lib/vad.ts` | Voice activity detector (end-of-utterance) |
| `app/src/stores/connection.ts` | Mode machine, mic recorder, all WS commands |
| `app/src-tauri/src/lib.rs` | Tauri shell: tray, hotkey, autostart plugin init |
| `app/src-tauri/tauri.conf.json` | Window chrome, bundle config |
| `app/src-tauri/capabilities/default.json` | Tauri permission allowlist |
