// Immersive-mode store: backdrop source, media stream, "live cognition"
// thought log. The actual <video>/<iframe> elements live in components
// and read from here.

import { create } from "zustand";
import { openRearCamera, openScreenShare } from "@/lib/vision";
import { useConnection } from "@/stores/connection";
import type { ImmersiveSource, ChartPayload, BacktestPayload } from "@/types";

export interface Thought {
  id: number;
  kind: "tool" | "hal" | "note";
  text: string;
  ts: number;
}

interface ImmersiveState {
  active: boolean;
  source: ImmersiveSource;
  stream: MediaStream | null;
  videoUrl: string | null;
  mapQuery: string;
  chart: ChartPayload | null;
  backtest: BacktestPayload | null;
  chartZoom: { from?: number; to?: number; reset?: boolean; nonce: number } | null;
  thoughts: Thought[];
  /** Frame-capture callback registered by ImmersiveStage. Returns a base64
   *  JPEG of the current backdrop frame, or null if no frame is available
   *  (e.g. map source, video still loading, tainted canvas). */
  frameProvider: (() => string | null) | null;
  setFrameProvider: (fn: (() => string | null) | null) => void;
  enter: () => Promise<void>;
  exit: () => void;
  setSource: (
    src: ImmersiveSource,
    payload?: { url?: string; query?: string; chart?: ChartPayload; backtest?: BacktestPayload },
  ) => Promise<void>;
  setMapQuery: (q: string) => void;
  setChartZoom: (z: { from?: number; to?: number; reset?: boolean }) => void;
  pushThought: (kind: Thought["kind"], text: string) => void;
  clearThoughts: () => void;
}

let nextId = 1;

function stopStream(stream: MediaStream | null) {
  if (!stream) return;
  for (const track of stream.getTracks()) {
    try {
      track.stop();
    } catch {
      /* ignore */
    }
  }
}

export const useImmersive = create<ImmersiveState>((set, get) => ({
  active: false,
  source: "off",
  stream: null,
  videoUrl: null,
  mapQuery: "New York, NY",
  chart: null,
  backtest: null,
  chartZoom: null,
  thoughts: [],
  frameProvider: null,

  setFrameProvider(fn) {
    set({ frameProvider: fn });
  },

  async enter() {
    if (get().active) return;
    document.body.classList.add("immersive");
    set({ active: true });
    get().pushThought("note", "Immersive mode engaged.");
    if (get().source === "off") await get().setSource("camera");
    // Push-to-talk: do NOT auto-start the mic on entering immersive. The user
    // holds the mic button to talk in every mode — no surprise hot mic.
  },

  exit() {
    stopStream(get().stream);
    document.body.classList.remove("immersive");
    set({ active: false, stream: null, source: "off", videoUrl: null });
    // Stop the mic on exit — we no longer want continuous listening.
    try {
      const conn = useConnection.getState();
      if (conn.recording) conn.stopRecording();
    } catch {
      /* ignore */
    }
  },

  async setSource(src, payload) {
    stopStream(get().stream);
    set({ stream: null, videoUrl: null });
    if (src === "off") {
      get().exit();
      return;
    }
    try {
      if (src === "camera") {
        const stream = await openRearCamera();
        set({ source: "camera", stream });
        get().pushThought("note", "Source: rear camera");
      } else if (src === "screen") {
        const stream = await openScreenShare();
        // If the user stops sharing from the browser bar, drop the source.
        stream.getVideoTracks()[0]?.addEventListener("ended", () => {
          if (get().source === "screen") get().setSource("off");
        });
        set({ source: "screen", stream });
        get().pushThought("note", "Source: screen share");
      } else if (src === "map") {
        const q = (payload?.query ?? get().mapQuery).trim() || "New York, NY";
        set({ source: "map", mapQuery: q });
        get().pushThought("note", `Source: map · ${q}`);
        get().pushThought(
          "note",
          "Note: HAL cannot see inside the map iframe. Use SCREEN to share the map for live vision.",
        );
      } else if (src === "video") {
        const url = (payload?.url ?? "").trim();
        if (!url) {
          get().pushThought("note", "Video source requires a URL.");
          return;
        }
        set({ source: "video", videoUrl: url });
        get().pushThought("note", `Source: video · ${url}`);
      } else if (src === "chart") {
        const chart = payload?.chart ?? get().chart;
        if (!chart) {
          get().pushThought("note", "Chart source requires a payload.");
          return;
        }
        set({ source: "chart", chart });
        get().pushThought("note", `Source: chart · ${chart.symbol} ${chart.timeframe}`);
      } else if (src === "backtest") {
        const backtest = payload?.backtest ?? get().backtest;
        if (!backtest) {
          get().pushThought("note", "Backtest source requires a payload.");
          return;
        }
        set({ source: "backtest", backtest });
        get().pushThought("note", `Source: backtest · ${backtest.underlying}`);
      }
    } catch (err) {
      get().pushThought("note", `Source error: ${(err as Error).message}`);
      console.warn("Immersive source error:", err);
    }
  },

  setMapQuery(q) {
    set({ mapQuery: q });
  },

  setChartZoom(z) {
    set({ chartZoom: { ...z, nonce: Date.now() } });
  },

  pushThought(kind, text) {
    if (!text) return;
    set((s) => ({
      thoughts: [
        ...s.thoughts.slice(-39),
        { id: nextId++, kind, text: text.slice(0, 600), ts: Date.now() },
      ],
    }));
  },

  clearThoughts() {
    set({ thoughts: [] });
  },
}));
