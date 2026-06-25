// Connection + voice-loop store. Owns the WebSocket, audio player, current
// mic recorder, and the live transcript / mode state. Components read from
// this store but never touch the WS directly.

import { create } from "zustand";
import { AudioPlayer } from "@/lib/audio";
import { Vad } from "@/lib/vad";
import { pickSupportedMimeType } from "@/lib/vision";
import { HalSocket, defaultWsUrl } from "@/lib/ws";
import { useImmersive } from "@/stores/immersive";
import { useUi } from "@/stores/ui";
import { usePositionSizing } from "@/stores/positionSizing";
import type {
  AlertEvent,
  Attachment,
  BrokerAccount,
  BrokerPosition,
  ChartPayload,
  ChatMessage,
  ConversationSummary,
  EquityFundamentals,
  McpServer,
  Mode,
  CommitteeStatus,
  NewsArticle,
  NewsWatch,
  RiskStatus,
  ServerEnvelope,
  Subscription,
  TelemetryEvent,
  TradeIdea,
} from "@/types";

export interface McpAddPayload {
  name: string;
  transport: string;
  server_command?: string;
  args?: string;
  url?: string;
  env?: string;
  headers?: string;
  api_key?: string;
}

interface ConnectionState {
  mode: Mode;
  stateLabel: string;
  subline: string;
  // Conversation history (server-authoritative).
  history: ChatMessage[];
  conversations: ConversationSummary[];
  currentId: string | null;
  // Optimistic pending HAL message indicator.
  pendingHal: boolean;
  telemetry: TelemetryEvent[];
  fastMode: boolean;
  // Stream + audio + recorder lifecycle.
  recording: boolean;
  /** Live mic MediaStream, exposed so visualizers (MicMeter) can attach
   *  their own AnalyserNode. Null when not recording. */
  micStream: MediaStream | null;
  liveVision: boolean;
  /** Mute HAL's voice output. Speech still streams + drives the state machine,
   *  it's just silenced. Persisted across restarts. */
  muted: boolean;
  /** Whether HAL may open the mic on his own (listen for a reply after asking
   *  a question, and keep hands-free immersive going). False = privacy mode.
   *  Persisted across restarts. */
  halListen: boolean;
  /** Quiet mode (do-not-disturb): server-authoritative. When on, HAL holds all
   *  proactive spoken alerts and stops volunteering trade ideas until lifted.
   *  Synced from the server (echoed on connect + on every toggle). */
  quiet: boolean;
  // MCP servers + market subscriptions (server-authoritative).
  mcpServers: McpServer[];
  subscriptions: Subscription[];
  subscriptionsConnected: boolean;
  subscriptionsUrl: string;
  alertEvents: AlertEvent[];
  newsWatches: NewsWatch[];
  newsArticles: NewsArticle[];
  // Pinned trade ideas / hold reads (newest first), so they don't scroll away
  // in the chat. Populated by the server's trade_idea messages.
  tradeIdeas: TradeIdea[];
  // "Place it" button state per trade-idea id: optimistic "placing" on click,
  // then "placed"/"failed" from the server's trade_placed message.
  tradePlacements: Record<string, "placing" | "placed" | "failed">;
  // Live brokerage view (Alpaca), for the Positions panel.
  positions: BrokerPosition[];
  brokerAccount: BrokerAccount | null;
  brokerReady: boolean;
  brokerPaper: boolean;
  tradeMode: string; // "confirm" | "autopilot"
  risk: RiskStatus | null;
  positionsError: string | null;
  // In-flight committee run progress (null when idle). startedAt is client-stamped.
  committeeStatus: (CommitteeStatus & { startedAt: number }) | null;
  // Equity-research fundamentals for the terminal's Equity/DCF tab, keyed by
  // symbol so switching tickers doesn't refetch ones we've already pulled.
  equity: Record<string, EquityFundamentals>;
  equityLoading: string | null; // symbol currently being fetched, else null
  // Daily candlestick payloads for the Equity tab, keyed by symbol (same caching
  // rationale as `equity`). Carries an `error` payload when a build fails.
  equityChart: Record<string, ChartPayload>;
  equityChartLoading: string | null;
}

interface ConnectionActions {
  init: () => Promise<void>;
  startRecording: (pushToTalk?: boolean) => Promise<void>;
  stopRecording: () => void;
  cancelRecording: () => void;
  abort: () => Promise<void>;
  wipe: () => Promise<void>;
  sendText: (text: string, attachments?: Attachment[]) => Promise<void>;
  newConversation: () => Promise<void>;
  switchConversation: (id: string) => Promise<void>;
  deleteConversation: (id: string) => Promise<void>;
  toggleFastMode: () => void;
  toggleMute: () => void;
  toggleHalListen: () => void;
  toggleQuiet: () => void;
  clearTelemetry: () => void;
  appendOptimisticUser: (content: string) => void;
  listMcp: () => void;
  addMcp: (payload: McpAddPayload) => void;
  removeMcp: (id: number) => void;
  toggleMcpServer: (id: number, enabled: boolean) => void;
  refreshMcp: () => void;
  authorizeMcp: (id: number) => void;
  listSubscriptions: () => void;
  removeNewsWatch: (watchId: number) => void;
  clearTradeIdeas: () => void;
  refreshWatchlist: () => void;
  refreshChart: () => void;
  refreshPositions: () => void;
  closePosition: (symbol: string) => void;
  scalePosition: (symbol: string, delta: number) => void;
  placeTrade: (id: string) => void;
  setTradeMode: (mode: "confirm" | "autopilot") => void;
  resetKillSwitch: () => void;
  loadEquity: (symbol: string) => void;
  loadEquityChart: (symbol: string) => void;
}

const STATE_LABELS: Record<Mode, string[]> = {
  idle: ["DORMANT", "STANDBY", "IDLE", "AWAITING", "READY"],
  connecting: ["ESTABLISHING LINK", "HANDSHAKE", "CONNECTING", "LINKING"],
  listening: ["RECEIVING", "LISTENING", "EARS OPEN", "INTAKE", "MIC LIVE"],
  processing: ["PROCESSING", "THINKING", "CRUNCHING", "COMPUTING", "PARSING"],
  speaking: ["TRANSMITTING", "SPEAKING", "BROADCASTING", "OUTPUT", "REPLYING"],
};

function pickLabel(mode: Mode): string {
  const opts = STATE_LABELS[mode];
  return opts[Math.floor(Math.random() * opts.length)];
}

// Sent with each turn so HAL tailors order steps to the chosen broker. Account
// total comes from Alpaca and risk policy from the vault trading rules, both
// read server-side — so only the broker rides along here.
function riskPayload() {
  const s = usePositionSizing.getState();
  return {
    broker: s.broker,
  };
}

// Mute preference persists across restarts (localStorage). Read once at module
// load so the AudioPlayer starts in the right state before the first chunk.
const MUTE_KEY = "hal.muted";
function loadMuted(): boolean {
  try {
    return localStorage.getItem(MUTE_KEY) === "1";
  } catch {
    return false;
  }
}
function saveMuted(muted: boolean): void {
  try {
    localStorage.setItem(MUTE_KEY, muted ? "1" : "0");
  } catch {
    /* ignore quota / unavailable storage */
  }
}

// Whether HAL may open the mic on his own — after asking a question, and to
// keep hands-free immersive going. Turning this off is the "privacy" /
// stop-listening switch. Persisted, defaults on.
const LISTEN_KEY = "hal.listen";
function loadHalListen(): boolean {
  try {
    return localStorage.getItem(LISTEN_KEY) !== "0";
  } catch {
    return true;
  }
}
function saveHalListen(listen: boolean): void {
  try {
    localStorage.setItem(LISTEN_KEY, listen ? "1" : "0");
  } catch {
    /* ignore quota / unavailable storage */
  }
}

// How long HAL keeps the mic open waiting for a reply to his question before
// standing down (no speech detected). Cancelled the moment the user speaks.
const QUESTION_LISTEN_MS = 10_000;

// Module-scoped infra. We keep this OUT of zustand state to avoid React
// trying to compare deep media-stream objects between renders.
const audio = new AudioPlayer();
audio.setMuted(loadMuted());
let socket: HalSocket | null = null;
let micStream: MediaStream | null = null;
let recorder: MediaRecorder | null = null;
let vad: Vad | null = null;
let streamDone = false;
// Patience timer for the post-question listen window (see armQuestionListen).
let questionListenTimer: number | null = null;
function clearQuestionListen() {
  if (questionListenTimer !== null) {
    clearTimeout(questionListenTimer);
    questionListenTimer = null;
  }
}

export const useConnection = create<ConnectionState & ConnectionActions>(
  (set, get) => {
    function setMode(mode: Mode, labelText?: string, transcriptText?: string) {
      const label = labelText ?? pickLabel(mode);
      set({ mode, stateLabel: label });
      // Reflect on <body> so CSS state selectors (.idle/.listening/...) work.
      const persistent: string[] = [];
      if (document.body.classList.contains("immersive"))
        persistent.push("immersive");
      if (document.body.classList.contains("fullscreen-chat"))
        persistent.push("fullscreen-chat");
      document.body.className = [mode, ...persistent].join(" ");
      if (transcriptText !== undefined) {
        set({ subline: mode === "idle" ? "" : transcriptText });
      } else if (mode === "idle") {
        set({ subline: "" });
      }
      // Auto-open the chat panel whenever a turn is in flight so the user
      // can see HAL's reply land. Idempotent if already open.
      if (mode === "processing" || mode === "speaking") {
        try {
          useUi.getState().setChatOpen(true);
        } catch {
          /* ignore */
        }
      }
    }

    // True when HAL's most recent reply ended on a question — our cue to open
    // the mic and wait for an answer.
    function halJustAskedQuestion(): boolean {
      const h = get().history;
      for (let i = h.length - 1; i >= 0; i--) {
        if (h[i].role === "assistant") {
          return h[i].content.trim().endsWith("?");
        }
      }
      return false;
    }

    // After HAL asks a question (outside hands-free immersive), open the mic
    // and listen for a reply. VAD's silence cutoff sends the turn once the user
    // speaks; if no one does, we stand down after QUESTION_LISTEN_MS so the mic
    // doesn't sit open indefinitely. The patience timer is cancelled the moment
    // speech starts (Vad.onSpeechStart, wired in startRecording).
    function armQuestionListen() {
      clearQuestionListen();
      void get().startRecording(false);
      questionListenTimer = window.setTimeout(() => {
        questionListenTimer = null;
        if (get().mode === "listening" && get().recording) {
          get().cancelRecording();
        }
      }, QUESTION_LISTEN_MS);
    }

    function maybeReturnToIdle() {
      if (!streamDone || audio.playing) return;
      setMode("idle", "DORMANT");
      // Privacy: when HAL is told to stop listening, never re-open the mic.
      if (!get().halListen) return;
      const immersive = useImmersive.getState().active;
      const questionAsked = !immersive && halJustAskedQuestion();
      // Hands-free immersive re-arms after every turn; outside immersive we only
      // re-open the mic when HAL just asked something. The delay is a post-speech
      // cooldown so the speaker's audio tail / room reverb doesn't instantly
      // re-trigger the VAD the moment HAL stops.
      if (!immersive && !questionAsked) return;
      try {
        window.setTimeout(() => {
          if (get().mode !== "idle" || get().recording || audio.playing) return;
          if (!get().halListen) return;
          if (useImmersive.getState().active) {
            void get().startRecording(false);
          } else if (questionAsked) {
            armQuestionListen();
          }
        }, 700);
      } catch {
        /* ignore */
      }
    }
    audio.onDrain(maybeReturnToIdle);

    function onJson(msg: ServerEnvelope) {
      if (msg.mcp_servers) {
        set({ mcpServers: msg.mcp_servers });
        return;
      }
      if (msg.subscriptions || msg.alert_events || msg.news_watches || msg.news_articles) {
        set({
          subscriptions: msg.subscriptions ?? [],
          subscriptionsConnected: !!msg.subscriptions_connected,
          subscriptionsUrl: msg.subscriptions_url ?? "",
          alertEvents: msg.alert_events ?? [],
          newsWatches: msg.news_watches ?? [],
          newsArticles: msg.news_articles ?? [],
        });
        return;
      }
      if (msg.quiet !== undefined) {
        set({ quiet: msg.quiet });
        return;
      }
      if (msg.broker_ready !== undefined) {
        set({
          positions: msg.positions ?? [],
          brokerAccount: msg.broker_account ?? null,
          brokerReady: !!msg.broker_ready,
          brokerPaper: msg.broker_paper ?? true,
          tradeMode: msg.trade_mode ?? "confirm",
          risk: msg.risk ?? null,
          positionsError: msg.positions_error ?? null,
        });
        return;
      }
      if (msg.telemetry) {
        set((s) => ({
          telemetry: [...s.telemetry, msg.telemetry!].slice(-300),
        }));
        return;
      }
      if (msg.committee_status) {
        const cs = msg.committee_status;
        set((s) => ({
          committeeStatus: cs.active
            ? { ...cs, startedAt: s.committeeStatus?.startedAt ?? Date.now() }
            : null,
        }));
        return;
      }
      if (msg.trade_idea) {
        // Pin it (newest first, capped) and open the trade-ideas immersive
        // stage so the reco doesn't get lost when the chat keeps scrolling.
        set((s) => ({
          tradeIdeas: [msg.trade_idea!, ...s.tradeIdeas].slice(0, 20),
        }));
        (async () => {
          const immersive = useImmersive.getState();
          await immersive.setSource("trade_ideas");
          if (!immersive.active) await immersive.enter();
        })().catch((err) => console.warn("trade_idea open:", err));
        return;
      }
      if (msg.equity) {
        const eq = msg.equity;
        set((s) => ({
          equity: { ...s.equity, [eq.symbol]: eq },
          equityLoading: s.equityLoading === eq.symbol ? null : s.equityLoading,
        }));
        return;
      }
      if (msg.equity_chart) {
        const ch = msg.equity_chart;
        set((s) => ({
          equityChart: { ...s.equityChart, [ch.symbol]: ch },
          equityChartLoading: s.equityChartLoading === ch.symbol ? null : s.equityChartLoading,
        }));
        return;
      }
      if (msg.trade_placed) {
        const { id, ok } = msg.trade_placed;
        set((s) => ({
          tradePlacements: { ...s.tradePlacements, [id]: ok ? "placed" : "failed" },
        }));
        return;
      }
      if (msg.conversations) {
        set({
          conversations: msg.conversations,
          currentId: msg.current_id ?? null,
        });
        return;
      }
      if (msg.conversation_history) {
        set({ history: msg.conversation_history, pendingHal: false });
        // Fresh history arrived — make sure the panel is open so the user
        // can actually see it (covers switch_conversation, new_conversation,
        // and initial connect).
        if (msg.conversation_history.length > 0) {
          try {
            useUi.getState().setChatOpen(true);
          } catch {
            /* ignore */
          }
        }
        return;
      }
      // Server preempted the current turn (e.g. an alert fired mid-speech) —
      // drop any audio still playing/queued so the new reply doesn't overlap.
      if (msg.action === "audio_flush") {
        audio.flush();
        return;
      }
      // Server→client action: HAL is driving the UI (e.g. open_view).
      if (msg.action === "open_view") {
        const kind = msg.kind ?? "";
        const query = msg.query ?? "";
        const chart = msg.chart;
        (async () => {
          const immersive = useImmersive.getState();
          // When the dashboard overlay is open it mirrors chart/backtest/
          // watchlist from this same store, so DON'T enter the immersive backdrop
          // — that would hijack the screen out from under the board. Just set the
          // data and let the dashboard tiles update in place.
          const dashOpen = useUi.getState().dashboardOpen;
          if (kind === "off") {
            immersive.exit();
            return;
          }
          if (kind === "chart") {
            // Set the chart source first so enter() doesn't flash the camera.
            await immersive.setSource("chart", { chart });
            if (!dashOpen && !immersive.active) await immersive.enter();
            return;
          }
          if (kind === "backtest") {
            await immersive.setSource("backtest", { backtest: msg.backtest });
            if (!dashOpen && !immersive.active) await immersive.enter();
            return;
          }
          if (kind === "watchlist") {
            await immersive.setSource("watchlist", { watchlist: msg.watchlist });
            if (!dashOpen && !immersive.active) await immersive.enter();
            return;
          }
          if (!immersive.active) await immersive.enter();
          if (kind === "map") {
            await immersive.setSource("map", { query });
          } else if (kind === "video") {
            await immersive.setSource("video", { url: query });
          } else if (kind === "camera" || kind === "screen") {
            await immersive.setSource(kind);
          } else {
            immersive.pushThought("note", `open_view: unknown kind "${kind}"`);
          }
        })().catch((err) => console.warn("open_view:", err));
        return;
      }
      // Server→client: toggle a useUi overlay panel (e.g. the dashboard).
      // Distinct from open_view, which drives the immersive backdrop.
      if (msg.action === "ui_panel") {
        const panel = msg.panel ?? "";
        const mode = msg.mode ?? "toggle"; // "show" | "hide" | "toggle"
        const ui = useUi.getState();
        if (panel === "dashboard") {
          if (mode === "show") ui.setDashboardOpen(true);
          else if (mode === "hide") ui.setDashboardOpen(false);
          else ui.toggleDashboard();
        }
        return;
      }
      // Live refresh of the watch-list board while it's open.
      if (msg.action === "watchlist_update") {
        if (msg.watchlist) useImmersive.getState().setWatchlist(msg.watchlist);
        return;
      }
      // Live refresh of the chart while it's open (preserves zoom client-side).
      if (msg.action === "chart_update") {
        if (msg.chart) useImmersive.getState().setChart(msg.chart);
        return;
      }
      if (msg.action === "chart_zoom") {
        useImmersive.getState().setChartZoom({
          from: msg.zoom_from,
          to: msg.zoom_to,
          reset: msg.zoom_reset,
        });
        return;
      }
      // Half-duplex: when HAL takes the floor (a reply or an injected alert)
      // while the hands-free mic is still armed, tear the mic down WITHOUT
      // sending — otherwise his own voice through the speakers (and room audio)
      // trips the VAD, which would preempt his turn and cut him off mid-sentence.
      // It re-arms via maybeReturnToIdle once he's done. (On a normal user turn
      // the recorder is already null here — onstop sent the turn first — so this
      // only fires when HAL starts talking on his own.)
      if ((msg.state === "processing" || msg.state === "speaking") && recorder) {
        get().cancelRecording();
      }
      if (msg.state === "listening") return;
      if (msg.state === "processing") {
        streamDone = false;
        return;
      }
      if (msg.state === "done") {
        streamDone = true;
        maybeReturnToIdle();
        return;
      }
      if (msg.state) {
        setMode(msg.state as Mode, undefined, msg.text);
      }
    }

    function getSocket(): HalSocket {
      if (socket) return socket;
      socket = new HalSocket(defaultWsUrl(), {
        onBinary: (buf) => {
          audio.queue(buf).catch((e) => console.warn("audio queue", e));
        },
        onJson,
        onError: () => setMode("idle", "ERROR", "Connection failed."),
        onClose: () => {
          // Soft close: only nudge UI if we weren't already idle.
          if (get().mode !== "idle" && !audio.playing) {
            setMode("idle", "DISCONNECTED", "Link dropped.");
          }
        },
      });
      return socket;
    }

    return {
      // -- initial state -----------------------------------------------
      mode: "idle",
      stateLabel: "DORMANT",
      subline: "All systems nominal. Awaiting input.",
      history: [],
      conversations: [],
      currentId: null,
      pendingHal: false,
      telemetry: [],
      fastMode: false,
      recording: false,
      micStream: null,
      liveVision: false,
      muted: loadMuted(),
      halListen: loadHalListen(),
      quiet: false, // server-authoritative; synced on connect via onJson

      mcpServers: [],
      subscriptions: [],
      subscriptionsConnected: false,
      subscriptionsUrl: "",
      alertEvents: [],
      newsWatches: [],
      newsArticles: [],
      tradeIdeas: [],
      tradePlacements: {},
      positions: [],
      brokerAccount: null,
      brokerReady: false,
      brokerPaper: true,
      tradeMode: "confirm",
      risk: null,
      positionsError: null,
      committeeStatus: null,
      equity: {},
      equityLoading: null,
      equityChart: {},
      equityChartLoading: null,

      // -- actions -----------------------------------------------------
      async init() {
        try {
          await getSocket().ensure();
        } catch (err) {
          console.warn("Pre-open WS failed:", err);
        }
      },

      async startRecording(pushToTalk = false) {
        if (get().mode === "listening") {
          // Already listening — caller is using button as a toggle.
          get().stopRecording();
          return;
        }
        try {
          await audio.ensureContext();
          setMode("connecting", "ESTABLISHING LINK");
          const sock = getSocket();
          await sock.ensure();
          await sock.sendCommand({ command: "start" });

          micStream = await navigator.mediaDevices.getUserMedia({
            audio: true,
          });
          set({ micStream });
          const mimeType = pickSupportedMimeType();
          recorder = mimeType
            ? new MediaRecorder(micStream, { mimeType })
            : new MediaRecorder(micStream);

          recorder.ondataavailable = (e) => {
            if (e.data.size > 0) sock.sendBinary(e.data);
          };
          recorder.onerror = (e) => {
            console.error("MediaRecorder:", e);
            setMode("idle", "ERROR", "Recorder error");
          };
          recorder.onstop = () => {
            // Live-vision: in immersive mode with a video source, capture
            // the current frame and attach it so HAL sees what you see.
            // Server already accepts attachments on the stop command and
            // wires images through to the vision LLM.
            const imm = useImmersive.getState();
            const attachments: Array<{
              name: string;
              kind: "image";
              content: string;
            }> = [];
            if (imm.active) {
              if (!imm.frameProvider) {
                imm.pushThought(
                  "note",
                  `No frame provider (source=${imm.source}) — HAL won't see this turn.`,
                );
              } else {
                const frame = imm.frameProvider();
                if (frame) {
                  attachments.push({
                    name: `live-${Date.now()}.jpg`,
                    kind: "image",
                    content: frame,
                  });
                  imm.pushThought(
                    "note",
                    `Frame captured (~${Math.round(frame.length / 1024)} KB) and attached.`,
                  );
                } else {
                  imm.pushThought(
                    "note",
                    `Frame capture returned null (video not ready or tainted canvas, source=${imm.source}).`,
                  );
                }
              }
            }
            sock.sendCommandSync({
              command: "stop",
              mime: recorder?.mimeType || mimeType || "",
              model_mode: get().fastMode ? "fast" : undefined,
              // Legacy used the faster vision model for live frames; manual
              // snaps don't. Match that.
              vision_mode: attachments.length > 0 ? "fast" : undefined,
              attachments: attachments.length > 0 ? attachments : undefined,
              risk: riskPayload(),
            });
            try {
              micStream?.getTracks().forEach((t) => t.stop());
            } catch {
              /* ignore */
            }
            micStream = null;
            recorder = null;
            set({ recording: false, micStream: null });
          };
          recorder.start(100);
          set({ recording: true });
          setMode("listening", "RECEIVING");

          // Push-to-talk: the user holds the button and releases to send, so
          // we do NOT auto-end on silence (they may pause mid-thought). The
          // button's onPointerUp calls stopRecording(). Click-toggle / immersive
          // hands-free mode keeps the silence-based VAD cutoff.
          if (!pushToTalk) {
            vad = new Vad(
              () => {
                // Half-duplex guard: if HAL is mid-turn (audio playing or
                // processing/speaking), a detected utterance is his own voice or
                // room noise — discard it instead of sending, so it can't cut
                // him off. Real barge-in is via the Stop button.
                const m = get().mode;
                if (audio.playing || m === "speaking" || m === "processing") {
                  get().cancelRecording();
                  return;
                }
                get().stopRecording();
              },
              {
                rmsThreshold: 0.018,
                silenceMs: 1200,
                // User started talking — commit to this turn; the post-question
                // patience timeout no longer applies.
                onSpeechStart: clearQuestionListen,
              },
            );
            vad.start(micStream);
          }
        } catch (err) {
          console.error("startRecording:", err);
          setMode("idle", "ERROR", (err as Error).message);
        }
      },

      stopRecording() {
        clearQuestionListen();
        vad?.stop();
        vad = null;
        if (recorder && recorder.state === "recording") {
          audio.flush();  // barge-in: cut HAL off before sending the new turn
          setMode("processing", "PROCESSING");
          set({ pendingHal: true });
          recorder.stop();
        }
      },

      cancelRecording() {
        // Tear down the mic without sending a turn. Detach onstop first so the
        // normal send-on-stop handler doesn't fire, then stop the tracks.
        clearQuestionListen();
        vad?.stop();
        vad = null;
        const r = recorder;
        recorder = null;
        if (r) {
          r.onstop = null;
          try {
            if (r.state !== "inactive") r.stop();
          } catch {
            /* ignore */
          }
        }
        try {
          micStream?.getTracks().forEach((t) => t.stop());
        } catch {
          /* ignore */
        }
        micStream = null;
        set({ recording: false, micStream: null });
        if (get().mode === "listening") setMode("idle", "DORMANT");
      },

      async abort() {
        try {
          await getSocket().sendCommand({ command: "abort" });
        } catch {
          /* ignore */
        }
        audio.flush();
        streamDone = true;
        setMode("idle", "DORMANT");
      },

      async wipe() {
        try {
          await getSocket().sendCommand({ command: "reset" });
          audio.flush();
          set({ telemetry: [], history: [], pendingHal: false });
          setMode("idle", "DORMANT", "Memory wiped.");
        } catch (err) {
          setMode("idle", "ERROR", `Wipe failed: ${(err as Error).message}`);
        }
      },

      async sendText(text, attachments = []) {
        const trimmed = text.trim();
        if (!trimmed && attachments.length === 0) return;
        audio.flush();  // stop any in-flight speech so voices don't overlap
        await audio.ensureContext();
        const sock = getSocket();
        await sock.sendCommand({
          command: "text",
          text: trimmed,
          attachments: attachments.map((a) => ({
            name: a.name,
            kind: a.kind,
            content: a.content,
          })),
          model_mode: get().fastMode ? "fast" : undefined,
          risk: riskPayload(),
        });
        get().appendOptimisticUser(
          trimmed ||
            (attachments.length
              ? `(${attachments.length} attachment${attachments.length > 1 ? "s" : ""})`
              : ""),
        );
        set({ pendingHal: true });
        setMode("processing", "PROCESSING");
      },

      appendOptimisticUser(content) {
        if (!content) return;
        set((s) => ({
          history: [...s.history, { role: "user", content }],
        }));
      },

      async newConversation() {
        await getSocket().sendCommand({ command: "new_conversation" });
        audio.flush();
        set({ history: [], telemetry: [], pendingHal: false });
        setMode("idle", "DORMANT", "(new conversation)");
      },
      async switchConversation(id) {
        await getSocket().sendCommand({ command: "switch_conversation", id });
        audio.flush();
        set({ pendingHal: false });
      },
      async deleteConversation(id) {
        await getSocket().sendCommand({ command: "delete_conversation", id });
      },

      toggleFastMode() {
        set((s) => ({ fastMode: !s.fastMode }));
      },

      toggleMute() {
        const muted = !get().muted;
        audio.setMuted(muted);
        saveMuted(muted);
        set({ muted });
      },

      toggleQuiet() {
        // Server owns the flag; toggle optimistically and let the server echo
        // confirm it (also keeps the button in sync with voice-driven toggles).
        const quiet = !get().quiet;
        set({ quiet });
        void getSocket().sendCommand({ command: "set_quiet", on: quiet });
      },

      toggleHalListen() {
        const halListen = !get().halListen;
        saveHalListen(halListen);
        set({ halListen });
        // Engaging privacy mid-listen: stand the mic down now, don't wait for
        // the next turn. Only tears down a HAL-opened listen (mode "listening"),
        // never an in-flight user turn.
        if (!halListen) {
          clearQuestionListen();
          if (get().recording && get().mode === "listening") {
            get().cancelRecording();
          }
        }
      },

      clearTelemetry() {
        set({ telemetry: [] });
      },

      listMcp() {
        void getSocket().sendCommand({ command: "mcp_list" });
      },
      addMcp(payload) {
        void getSocket().sendCommand({ command: "mcp_add", ...payload });
      },
      removeMcp(id) {
        void getSocket().sendCommand({ command: "mcp_remove", id });
      },
      toggleMcpServer(id, enabled) {
        void getSocket().sendCommand({ command: "mcp_toggle", id, enabled });
      },
      refreshMcp() {
        void getSocket().sendCommand({ command: "mcp_refresh" });
      },
      authorizeMcp(id) {
        void getSocket().sendCommand({ command: "mcp_authorize", id });
      },
      listSubscriptions() {
        void getSocket().sendCommand({ command: "list_subscriptions" });
      },
      removeNewsWatch(watchId) {
        void getSocket().sendCommand({
          command: "news_remove_watch",
          watch_id: watchId,
        });
      },
      clearTradeIdeas() {
        set({ tradeIdeas: [] });
      },
      refreshWatchlist() {
        void getSocket().sendCommand({ command: "watchlist_refresh" });
      },
      refreshChart() {
        void getSocket().sendCommand({ command: "chart_refresh" });
      },
      refreshPositions() {
        void getSocket().sendCommand({ command: "positions_refresh" });
      },
      closePosition(symbol) {
        void getSocket().sendCommand({ command: "position_close", symbol });
      },
      scalePosition(symbol, delta) {
        if (!delta) return;
        void getSocket().sendCommand({ command: "scale_position", symbol, delta });
      },
      placeTrade(id) {
        set((s) => ({
          tradePlacements: { ...s.tradePlacements, [id]: "placing" },
        }));
        void getSocket().sendCommand({ command: "place_trade", id });
      },
      setTradeMode(mode) {
        void getSocket().sendCommand({ command: "set_trade_mode", mode });
      },
      resetKillSwitch() {
        void getSocket().sendCommand({ command: "reset_kill_switch" });
      },
      loadEquity(symbol) {
        const sym = symbol.toUpperCase().trim();
        if (!sym) return;
        set({ equityLoading: sym });
        void getSocket().sendCommand({ command: "equity_fundamentals", symbol: sym });
      },
      loadEquityChart(symbol) {
        const sym = symbol.toUpperCase().trim();
        if (!sym) return;
        set({ equityChartLoading: sym });
        void getSocket().sendCommand({ command: "equity_chart", symbol: sym, timeframe: "1d" });
      },
    };
  },
);
