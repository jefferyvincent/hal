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
import ImmersiveStage from "@/components/immersive/ImmersiveStage";
import SourceBar from "@/components/immersive/SourceBar";
import MapInput from "@/components/immersive/MapInput";
import ThoughtsPanel from "@/components/immersive/ThoughtsPanel";
import { useConnection } from "@/stores/connection";
import { useImmersive } from "@/stores/immersive";

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
