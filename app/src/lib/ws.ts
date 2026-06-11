// HAL voice WebSocket client. The server speaks two languages over /ws:
//
//   * Binary frames: WAV chunks (TTS playback). Forwarded to AudioPlayer.
//   * Text frames: JSON envelopes (state, telemetry, conversations, ...).
//
// The client sends:
//
//   * Binary frames: mic audio chunks from MediaRecorder.
//   * Text frames: JSON commands ({ command: "start" | "stop" | "abort" |
//     "text" | "reset" | "new_conversation" | "switch_conversation" |
//     "delete_conversation" }).

import type { ServerEnvelope } from "@/types";

export interface WsHandlers {
  onBinary: (buffer: ArrayBuffer) => void;
  onJson: (msg: ServerEnvelope) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (e: Event) => void;
}

export class HalSocket {
  private url: string;
  private ws: WebSocket | null = null;
  private handlers: WsHandlers;
  private connecting: Promise<WebSocket> | null = null;

  constructor(url: string, handlers: WsHandlers) {
    this.url = url;
    this.handlers = handlers;
  }

  async ensure(): Promise<WebSocket> {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) return this.ws;
    if (this.connecting) return this.connecting;
    this.connecting = new Promise<WebSocket>((resolve, reject) => {
      const ws = new WebSocket(this.url);
      ws.binaryType = "arraybuffer";
      const onOpen = () => {
        ws.removeEventListener("open", onOpen);
        ws.removeEventListener("error", onError);
        this.handlers.onOpen?.();
        resolve(ws);
      };
      const onError = (e: Event) => {
        ws.removeEventListener("open", onOpen);
        ws.removeEventListener("error", onError);
        this.handlers.onError?.(e);
        reject(new Error("WebSocket connection failed"));
      };
      ws.addEventListener("open", onOpen);
      ws.addEventListener("error", onError);
      ws.addEventListener("message", (event) => {
        if (event.data instanceof ArrayBuffer) {
          this.handlers.onBinary(event.data);
        } else {
          try {
            this.handlers.onJson(JSON.parse(event.data));
          } catch (err) {
            console.error("HalSocket: bad JSON", err, event.data);
          }
        }
      });
      ws.addEventListener("close", () => {
        if (this.ws === ws) this.ws = null;
        this.handlers.onClose?.();
      });
      this.ws = ws;
    }).finally(() => {
      this.connecting = null;
    });
    return this.connecting;
  }

  /** Best-effort send of a JSON command. Resolves when connected. */
  async sendCommand(payload: Record<string, unknown>): Promise<void> {
    const ws = await this.ensure();
    ws.send(JSON.stringify(payload));
  }

  sendCommandSync(payload: Record<string, unknown>): boolean {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload));
      return true;
    }
    return false;
  }

  sendBinary(data: BlobPart): boolean {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(data as Blob);
      return true;
    }
    return false;
  }

  close() {
    try {
      this.ws?.close();
    } catch {
      /* ignore */
    }
    this.ws = null;
  }

  get readyState(): number {
    return this.ws?.readyState ?? WebSocket.CLOSED;
  }
}

/** Decide which URL to talk to.
 *  - Vite dev (`http://localhost:1420/`): same-origin, proxy forwards /ws.
 *  - FastAPI static serve (`http://localhost:8000/`): same-origin.
 *  - Tauri webview (`http(s)://tauri.localhost/`): server is on a separate
 *    port — never same-origin. Hit localhost:8000 directly.
 *  - file:// fallback: localhost:8000. */
export function defaultWsUrl(): string {
  const loc = window.location;
  const isTauri =
    loc.hostname === "tauri.localhost" ||
    typeof (window as unknown as { __TAURI_INTERNALS__?: unknown })
      .__TAURI_INTERNALS__ !== "undefined";
  if (!isTauri && (loc.protocol === "http:" || loc.protocol === "https:")) {
    const proto = loc.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${loc.host}/ws`;
  }
  return "ws://localhost:8000/ws";
}
