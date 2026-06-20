import { useEffect, useRef } from "react";
import Hud from "@/components/Hud";
import Footer from "@/components/Footer";
import Eye from "@/components/Eye";
import Controls from "@/components/Controls";
import MicMeter from "@/components/MicMeter";
import WindowControls from "@/components/WindowControls";
import InputBar from "@/components/InputBar";
import Transcript from "@/components/Transcript";
import ConversationsPanel from "@/components/ConversationsPanel";
import TelemetryPanel from "@/components/TelemetryPanel";
import CognitionStage from "@/components/CognitionStage";
import PositionSizing from "@/components/PositionSizing";
import PositionsPanel from "@/components/PositionsPanel";
import McpPanel from "@/components/McpPanel";
import SubscriptionsPanel from "@/components/SubscriptionsPanel";
import TradeIdeasStage from "@/components/TradeIdeasPanel";
import ImmersiveStage from "@/components/immersive/ImmersiveStage";
import SourceBar from "@/components/immersive/SourceBar";
import MapInput from "@/components/immersive/MapInput";
import ThoughtsPanel from "@/components/immersive/ThoughtsPanel";
import { useConnection } from "@/stores/connection";
import { useImmersive } from "@/stores/immersive";
import { useUi } from "@/stores/ui";
import { isMarketOpen } from "@/lib/marketSession";
import { playMarketBell } from "@/lib/bell";

export default function App() {
  const init = useConnection((s) => s.init);
  const telemetry = useConnection((s) => s.telemetry);
  const history = useConnection((s) => s.history);
  const immersiveActive = useImmersive((s) => s.active);
  const pushThought = useImmersive((s) => s.pushThought);

  // Open the WebSocket on mount so the conversations list populates before
  // the user clicks anything.
  useEffect(() => {
    void init();
  }, [init]);

  // Register HAL with Windows startup apps (production Tauri builds only —
  // skip in `npm run dev` so the dev binary doesn't get pinned to logon).
  useEffect(() => {
    if (!import.meta.env.PROD) return;
    (async () => {
      const { isEnabled, enable } = await import("@tauri-apps/plugin-autostart");
      if (!(await isEnabled())) await enable();
    })().catch((err) => console.warn("autostart:", err));
  }, []);

  // Mirror telemetry events into the immersive thoughts panel.
  const lastTelemetryLen = useRef(0);
  useEffect(() => {
    if (!immersiveActive) {
      lastTelemetryLen.current = telemetry.length;
      return;
    }
    for (let i = lastTelemetryLen.current; i < telemetry.length; i++) {
      const t = telemetry[i];
      const tag = `${t.tool}${t.status && t.status !== "ok" ? " · " + t.status : ""}`;
      pushThought("tool", `▶ ${tag}`);
      if (t.output) {
        const head = t.output.split("\n").slice(0, 2).join(" ").trim();
        if (head) pushThought("note", head.slice(0, 200));
      }
    }
    lastTelemetryLen.current = telemetry.length;
  }, [telemetry, immersiveActive, pushThought]);

  // Auto-open the Cognition view when the committee convenes, so the desk's
  // reasoning unfolds on screen. Once per turn: a new question resets the latch,
  // and closing it mid-run won't yank it back open.
  const cogScanLen = useRef(0);
  const autoOpenedRef = useRef(false);
  useEffect(() => {
    const setCognitionOpen = useUi.getState().setCognitionOpen;
    for (let i = cogScanLen.current; i < telemetry.length; i++) {
      const t = telemetry[i];
      if (t.tool === "human.question") autoOpenedRef.current = false;
      if (
        t.source === "committee" &&
        !autoOpenedRef.current &&
        !useUi.getState().cognitionOpen
      ) {
        autoOpenedRef.current = true;
        setCognitionOpen(true);
      }
    }
    cogScanLen.current = telemetry.length;
  }, [telemetry]);

  // Mirror final HAL messages too.
  const lastHistoryLen = useRef(0);
  useEffect(() => {
    if (!immersiveActive) {
      lastHistoryLen.current = history.length;
      return;
    }
    if (
      history.length > lastHistoryLen.current &&
      history[history.length - 1]?.role === "assistant"
    ) {
      pushThought("hal", history[history.length - 1].content);
    }
    lastHistoryLen.current = history.length;
  }, [history, immersiveActive, pushThought]);

  // Ring the NYSE-style bell on the regular-session open (9:30 ET) and close
  // (16:00 ET). Polls the client clock; the first read only seeds state so a
  // page load mid-session doesn't ring. Holidays aren't accounted for (same
  // caveat as the server's markettime helper).
  const wasOpen = useRef<boolean | null>(null);
  useEffect(() => {
    const check = () => {
      const open = isMarketOpen();
      if (wasOpen.current !== null && open !== wasOpen.current) {
        playMarketBell(open ? "open" : "close");
      }
      wasOpen.current = open;
    };
    check();
    const id = window.setInterval(check, 15_000);
    return () => window.clearInterval(id);
  }, []);

  // ESC exits immersive (when not focused in an input).
  const exitImmersive = useImmersive((s) => s.exit);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      const t = e.target as HTMLElement | null;
      if (
        t &&
        (t.tagName === "INPUT" ||
          t.tagName === "TEXTAREA" ||
          t.isContentEditable)
      )
        return;
      if (useImmersive.getState().active) exitImmersive();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [exitImmersive]);

  return (
    <div className="crt-scanlines crt-vignette relative h-full w-full">
      <div className="crt-grid" aria-hidden />

      {/* Immersive backdrop sits at z-3, above grid but under HUD. */}
      <ImmersiveStage />
      <SourceBar />
      <MapInput />
      <ThoughtsPanel />

      <Hud />
      <WindowControls />

      <ConversationsPanel />
      <TelemetryPanel />
      {/* Cognition: full-screen holographic decision-flow (HAL + committee + broker + human). */}
      <CognitionStage />
      {/* Risk-based options position sizing (account size + risk rules). */}
      <PositionSizing />
      <SubscriptionsPanel />
      <TradeIdeasStage />
      <McpPanel />
      {/* Live brokerage positions + manual close (overrides HAL). */}
      <PositionsPanel />

      <main
        className={`relative z-[5] flex h-full w-full items-center justify-center pt-[70px] pb-[260px] ${
          immersiveActive ? "pointer-events-none" : ""
        }`}
      >
        <Eye />
      </main>
      <Transcript />

      <MicMeter />
      <Controls />
      <InputBar />
      <Footer />
    </div>
  );
}
