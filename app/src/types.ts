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
  /** Which actor produced this event — drives the Cognition view's source lanes. */
  source?: "hal" | "committee" | "broker" | "human" | "risk" | string;
  /** Epoch milliseconds when the server emitted it. */
  ts?: number;
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
  /** Result of a "Place it" button click, so its button can flip placed/failed. */
  trade_placed?: { id: string; ok: boolean };
  /** Live brokerage view (reply to positions_refresh / position_close). */
  positions?: BrokerPosition[];
  broker_account?: BrokerAccount | null;
  broker_ready?: boolean;
  broker_paper?: boolean;
  trade_mode?: string; // "confirm" | "autopilot"
  positions_error?: string | null;
  risk?: RiskStatus;
  /** Quiet mode (do-not-disturb) state — echoed by the server on connect and
   *  whenever it's toggled by voice or the HUD button. */
  quiet?: boolean;
  /** Live committee-run progress for the Cognition view's completion bar. */
  committee_status?: CommitteeStatus;
  /** Equity-research fundamentals snapshot (reply to equity_fundamentals). */
  equity?: EquityFundamentals;
  /** Standalone candlestick payload for the Equity tab (reply to equity_chart). */
  equity_chart?: ChartPayload;
  /** Market-movers board for the Heatmap tab (reply to movers_refresh). */
  movers?: MoversPayload;
  /** Autonomous scalper session snapshot; null when no session is running. */
  scalper_status?: ScalperStatus | null;
}

/** Company fundamentals for the terminal's Equity Research / DCF tab, built
 *  server-side by hal/sensory/fundamentals.py from Nasdaq's keyless endpoints.
 *  Any field may be null when the source omits it — the UI degrades gracefully
 *  and the client runs the DCF from whatever's present. Money values are in the
 *  reporting currency's base units (dollars, not millions). */
export interface EquityFundamentals {
  symbol: string;
  name: string | null;
  as_of: number; // unix seconds
  price: number | null;
  currency: string | null;
  market_cap: number | null;
  shares_outstanding: number | null;
  sector: string | null;
  industry: string | null;
  region: string | null;
  description: string | null;
  /** Mean 1-year analyst price target. */
  target_price: number | null;
  /** Analyst coverage: consensus rating, analyst count, covering broker firms. */
  analyst: {
    rating: string | null; // e.g. "Buy"
    count: number | null; // analysts offering recommendations
    brokers: string[]; // broker firm names (drives the coverage graph)
  } | null;
  summary: {
    pe: number | null;
    eps: number | null;
    dividend_yield: number | null; // fraction, e.g. 0.012
    beta: number | null;
    week52_high: number | null;
    week52_low: number | null;
    volume: number | null;
    avg_volume: number | null;
    change: number | null; // intraday net change in price
    change_pct: number | null; // intraday change as a fraction
    day_high: number | null;
    day_low: number | null;
    prev_close: number | null;
  };
  /** Annual statements, newest first. */
  annual: EquityYear[];
  error: string | null;
}

export interface EquityYear {
  year: string; // fiscal year label, e.g. "2024"
  revenue: number | null;
  gross_profit: number | null;
  operating_income: number | null;
  net_income: number | null;
  operating_cash_flow: number | null;
  capex: number | null; // positive magnitude of capital expenditure
  free_cash_flow: number | null; // operating_cash_flow - capex when both present
  total_debt: number | null;
  cash: number | null;
}

/** Progress of an in-flight committee run, streamed per desk step. */
export interface CommitteeStatus {
  active: boolean;
  fraction?: number; // 0..1 completion
  label?: string; // current stage, e.g. "Bull researcher"
  symbol?: string;
}

/** Autonomous scalper session snapshot, from cerebellum.scalper.status(). */
export interface ScalperStatus {
  status: string; // running|market_closed|target_hit|floor_hit|stopped|error|idle
  realized_pnl: number;
  unrealized_pnl: number;
  total_pnl: number;
  profit_target: number;
  loss_limit: number;
  period: string; // "day" | "week"
  period_key: string;
  /** symbol -> side ("buy" | "sell") for positions the session opened. */
  open_positions: Record<string, string>;
  passes: number;
  note: string;
}

/** Pre-trade risk engine snapshot, from sensory.risk.status(). */
export interface RiskStatus {
  killed: boolean;
  kill_reason: string;
  orders_last_min: number;
  baseline_equity: number | null;
  limits: {
    max_orders_per_min: number;
    max_open_positions: number;
    max_gross_exposure_pct: number;
    daily_loss_limit_pct: number;
  };
}

/** An open brokerage position (Alpaca), as shaped by broker.list_positions. */
export interface BrokerPosition {
  symbol: string;
  asset_class: string; // "us_equity" | "us_option" | ...
  qty: string;
  side: string; // "long" | "short"
  avg_entry_price: number | null;
  current_price: number | null;
  market_value: number | null;
  unrealized_pl: number | null;
  unrealized_plpc: number | null; // fraction, e.g. 0.0125 = +1.25%
}

/** Alpaca account snapshot (subset), from broker.get_account. */
export interface BrokerAccount {
  account_number: string;
  status: string;
  currency: string;
  cash: number | null;
  equity: number | null;
  buying_power: number | null;
  options_buying_power: number | null;
  options_trading_level: number | null;
  pattern_day_trader: boolean;
  paper: boolean;
}

/** A pinned trade recommendation or hold/exit read for the Trade Ideas pane. */
export interface TradeIdea {
  id: string;
  kind: "trade" | "hold";
  symbol: string;
  /** Markdown body (the same table/read shown in chat). */
  markdown: string;
  ts: number; // unix seconds
  /** True when Alpaca is live and HAL staged this exact order — a "Place it"
   *  button can submit it directly (no speech). */
  placeable?: boolean;
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

/** A single market-mover tile for the terminal's Heatmap tab. change_pct is in
 *  percent units (e.g. 4.82 = +4.82%). category is "Gainer" | "Loser" | "Active"
 *  | "NDX". Built server-side by hal/sensory/movers.py from Nasdaq's keyless feed. */
export interface MoversRow {
  symbol: string;
  name?: string | null;
  price?: number | null;
  change_pct: number;
  category: string;
  error?: string | null;
}

export interface MoversPayload {
  rows: MoversRow[];
  generated_at: number;
  as_of?: string | null;
  error?: string | null;
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
  /** Set instead of the series fields when the build failed (equity_chart path). */
  error?: string;
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
