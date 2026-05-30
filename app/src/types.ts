// Shared types for the HAL voice client.

export type Mode = "idle" | "connecting" | "listening" | "processing" | "speaking";

export interface ConversationSummary {
  id: string;
  title: string;
  message_count?: number;
  updated_at?: number; // seconds since epoch
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface TelemetryEvent {
  tool: string;
  status?: "ok" | "error" | "declined" | string;
  input?: string;
  output?: string;
}

export interface Attachment {
  name: string;
  kind: "image" | "text";
  /** base64 (image) or raw text (text) */
  content: string;
}

/** Incoming JSON message envelope from the server. The server is loose with
 *  this shape — every key is independently optional. */
export interface ServerEnvelope {
  state?: Mode | "done";
  text?: string;
  telemetry?: TelemetryEvent;
  conversations?: ConversationSummary[];
  current_id?: string;
  conversation_history?: ChatMessage[];
  /** Server-driven UI action (e.g. open_view). HAL uses this via the
   *  `open_view` tool to actually show maps / camera / screen inside the
   *  immersive backdrop instead of just describing them. */
  action?: string;
  kind?: string;
  query?: string;
  /** Candlestick chart payload (action="open_view", kind="chart"). */
  chart?: ChartPayload;
  /** Chart zoom command (action="chart_zoom"); times are unix seconds. */
  zoom_from?: number;
  zoom_to?: number;
  zoom_reset?: boolean;
}

export type ImmersiveSource = "off" | "camera" | "screen" | "map" | "video" | "chart";

/** Candlestick chart payload built server-side by charting.py. Times are
 *  unix SECONDS (lightweight-charts UTCTimestamp). */
export interface ChartPayload {
  symbol: string;
  timeframe: string;
  bar_count: number;
  candles: { time: number; open: number; high: number; low: number; close: number }[];
  volume: { time: number; value: number; up: boolean }[];
  supertrend_up: { time: number; value: number }[];
  supertrend_down: { time: number; value: number }[];
  markers: { time: number; side: "buy" | "sell" }[];
  levels: { price: number; kind: "support" | "resistance"; label: string }[];
}
