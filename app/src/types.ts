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
}

export type ImmersiveSource = "off" | "camera" | "screen" | "map" | "video";
