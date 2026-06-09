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
  /** UI panel control (action="ui_panel"): which panel and show/hide/toggle. */
  panel?: string;
  mode?: string;
  /** Candlestick chart payload (action="open_view", kind="chart"). */
  chart?: ChartPayload;
  /** Watch-list board payload (action="open_view" kind="watchlist" or "watchlist_update"). */
  watchlist?: WatchlistPayload;
  /** Chart zoom command (action="chart_zoom"); times are unix seconds. */
  zoom_from?: number;
  zoom_to?: number;
  zoom_reset?: boolean;
  /** Backtest equity-curve payload (action="open_view", kind="backtest"). */
  backtest?: BacktestPayload;
  /** Configured MCP servers + live status (reply to mcp_list / mcp_*). */
  mcp_servers?: McpServer[];
  /** Active market subscriptions + their alert rules (reply to list_subscriptions). */
  subscriptions?: Subscription[];
  subscriptions_connected?: boolean;
  subscriptions_url?: string;
  /** Recently fired alerts. */
  alert_events?: AlertEvent[];
  /** Per-symbol news watch list + recently captured headlines. */
  news_watches?: NewsWatch[];
  news_articles?: NewsArticle[];
  /** A trade idea / hold read to pin in the Trade Ideas pane. */
  trade_idea?: TradeIdea;
}

/** A pinned trade recommendation or hold/exit read for the Trade Ideas pane. */
export interface TradeIdea {
  id: string;
  kind: "trade" | "hold";
  symbol: string;
  /** Markdown body (the same table/read shown in chat). */
  markdown: string;
  ts: number; // unix seconds
}

export type ImmersiveSource = "off" | "camera" | "screen" | "map" | "video" | "chart" | "backtest" | "watchlist" | "trade_ideas";

export interface WatchlistRow {
  symbol: string;
  price?: number | null;
  change_pct?: number | null;
  volume?: number | null;
  news_count: number;
  latest_headline?: string | null;
  latest_at?: number | null;
  error?: string | null;
}

export interface WatchlistPayload {
  rows: WatchlistRow[];
  generated_at: number;
}

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

/** Backtest equity-curve payload built server-side by backtest.py. Times
 *  (t) are unix SECONDS. */
export interface BacktestPayload {
  kind: "backtest";
  underlying: string;
  strategy: string;
  equity: { t: number; value: number }[];
  metrics: Record<string, number | null>;
  by_regime: Record<string, { trades: number; win_rate: number; avg_pnl: number }>;
}

// --- MCP servers ----------------------------------------------------------

export interface McpToolInfo {
  name: string;
  description: string;
}

export type McpStatus =
  | "connected"
  | "needs_auth"
  | "error"
  | "connecting"
  | "disabled"
  | "unknown";

export interface McpServer {
  id: number;
  name: string;
  slug: string;
  transport: "stdio" | "http" | string;
  command?: string | null;
  url?: string | null;
  enabled: boolean;
  status: McpStatus;
  error?: string | null;
  tools: McpToolInfo[];
  tool_count: number;
}

// --- Market subscriptions & alerts ---------------------------------------

export interface AlertRule {
  id: number;
  rule_type: string;
  config: Record<string, unknown> | string;
  note?: string | null;
  active: number;
  triggered_count: number;
  last_triggered_at?: number | null;
  cooldown_seconds: number;
  created_at: number;
}

export interface Subscription {
  id: number;
  channel: string;
  symbol: string;
  note?: string | null;
  created_at: number;
  active: number;
  rules: AlertRule[];
}

export interface AlertEvent {
  id: number;
  rule_id: number;
  fired_at: number;
  message: string;
  spoken: number;
  channel: string;
  symbol: string;
}

export interface NewsWatch {
  id: number;
  symbol: string;
  keywords?: string | null;
  note?: string | null;
  created_at: number;
  active: number;
  last_polled_at?: number | null;
  article_count: number;
}

export interface NewsArticle {
  id: number;
  watch_id: number;
  symbol: string;
  title: string;
  url: string;
  source?: string | null;
  published_at?: number | null;
  summary?: string | null;
  seen_at: number;
  spoken: number;
}
