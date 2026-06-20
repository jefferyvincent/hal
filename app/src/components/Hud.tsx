import { useEffect, useState } from "react";
import { useConnection } from "@/stores/connection";
import { useUi } from "@/stores/ui";
import { useImmersive } from "@/stores/immersive";
import { cn } from "@/lib/cn";

function formatUptime(ms: number): string {
  const s = Math.floor(ms / 1000);
  const h = String(Math.floor(s / 3600)).padStart(2, "0");
  const m = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  const sec = String(s % 60).padStart(2, "0");
  return `${h}:${m}:${sec}`;
}

const BOOT = Date.now();

// Shared HUD button styling. Resting state is brighter than before (border/55 +
// bg/12, larger label/value text) so the controls are legible before hover.
const HUD_BTN =
  "flex flex-col gap-[3px] border px-3.5 py-[7px] uppercase tracking-[4px] transition-colors";
const HUD_BTN_RED =
  "border-hal-red/55 bg-hal-red/[0.12] hover:border-hal-red hover:bg-hal-red/25 hover:shadow-[0_0_16px_rgba(255,30,30,0.5)]";
const HUD_BTN_AMBER =
  "border-hal-amber/55 bg-hal-amber/[0.12] hover:border-hal-amber hover:bg-hal-amber/25 hover:shadow-[0_0_16px_rgba(255,176,0,0.5)]";
// Lit-up state for toggles that are "on" (autopilot armed, voice muted).
const HUD_BTN_ACTIVE =
  "border-hal-amber bg-hal-amber/25 shadow-[0_0_16px_rgba(255,176,0,0.6)] hover:bg-hal-amber/35";
const HUD_LABEL = "text-[10px]";
const HUD_VALUE = "text-[12px] font-bold text-white";

export default function Hud() {
  const [uptime, setUptime] = useState("00:00:00");
  const stateLabel = useConnection((s) => s.stateLabel);
  const subline = useConnection((s) => s.subline);
  const toggleConv = useUi((s) => s.toggleConversations);
  const toggleMcp = useUi((s) => s.toggleMcp);
  const toggleSubscriptions = useUi((s) => s.toggleSubscriptions);
  const togglePositions = useUi((s) => s.togglePositions);
  const toggleCognition = useUi((s) => s.toggleCognition);
  const tradeMode = useConnection((s) => s.tradeMode);
  const setTradeMode = useConnection((s) => s.setTradeMode);
  const risk = useConnection((s) => s.risk);
  const resetKillSwitch = useConnection((s) => s.resetKillSwitch);
  const killed = !!risk?.killed;
  const muted = useConnection((s) => s.muted);
  const toggleMute = useConnection((s) => s.toggleMute);
  const autopilot = tradeMode === "autopilot";
  // Trade ideas live in the immersive stage: toggle that source on/off.
  const toggleTradeIdeas = () => {
    const im = useImmersive.getState();
    if (im.active && im.source === "trade_ideas") {
      im.exit();
    } else {
      void im.setSource("trade_ideas").then(() => {
        if (!useImmersive.getState().active) void useImmersive.getState().enter();
      });
    }
  };

  useEffect(() => {
    const id = window.setInterval(
      () => setUptime(formatUptime(Date.now() - BOOT)),
      1000,
    );
    return () => clearInterval(id);
  }, []);

  return (
    <header
      data-tauri-drag-region
      className="immersive-fade fixed left-0 right-0 top-0 z-10 flex items-center justify-between px-8 py-5 text-[10px] uppercase tracking-[4px] text-hal-text-dim"
    >
      <div className="flex gap-6">
        <div className="flex flex-col gap-[3px]">
          <div className="text-[9px] text-hal-red/60">VESSEL</div>
          <div className="text-hal-text">DISCOVERY ONE</div>
        </div>
        <div className="flex flex-col gap-[3px]">
          <div className="text-[9px] text-hal-red/60">UNIT</div>
          <div className="text-hal-text">HAL 9000</div>
        </div>
      </div>

      <div className="flex items-center gap-6">
        <div className="flex flex-col gap-[3px]">
          <div className="text-[9px] text-hal-red/60">SYS STATE</div>
          <div className="font-bold text-white" title={subline}>
            {stateLabel}
          </div>
          {subline ? (
            <div
              id="statusSubline"
              className="max-w-[40ch] truncate text-[8px] text-hal-text-dim"
            >
              {subline}
            </div>
          ) : null}
        </div>
        <div className="flex flex-col gap-[3px]">
          <div className="text-[9px] text-hal-red/60">UPTIME</div>
          <div className="text-hal-text">{uptime}</div>
        </div>
        {/* Mute HAL's voice. Speech still streams + drives the eye/state, just
            silenced. Amber when muted so it reads as an active override. */}
        <button
          type="button"
          onClick={toggleMute}
          data-tauri-drag-region="false"
          title={
            muted
              ? "HAL's voice is MUTED. Click to unmute."
              : "Mute HAL's voice."
          }
          className={cn(HUD_BTN, muted ? HUD_BTN_ACTIVE : HUD_BTN_RED)}
        >
          <span className={cn(HUD_LABEL, muted ? "text-hal-amber" : "text-hal-red")}>
            VOICE
          </span>
          <span className={HUD_VALUE}>{muted ? "MUTED" : "ON"}</span>
        </button>
        <button
          type="button"
          onClick={toggleConv}
          data-tauri-drag-region="false"
          className={cn(HUD_BTN, HUD_BTN_RED)}
        >
          <span className={cn(HUD_LABEL, "text-hal-red")}>CHATS</span>
          <span className={HUD_VALUE}>OPEN</span>
        </button>
        <button
          type="button"
          onClick={toggleSubscriptions}
          data-tauri-drag-region="false"
          className={cn(HUD_BTN, HUD_BTN_RED)}
        >
          <span className={cn(HUD_LABEL, "text-hal-red")}>WATCHES</span>
          <span className={HUD_VALUE}>OPEN</span>
        </button>
        <button
          type="button"
          onClick={togglePositions}
          data-tauri-drag-region="false"
          className={cn(HUD_BTN, HUD_BTN_RED)}
        >
          <span className={cn(HUD_LABEL, "text-hal-red")}>POSITIONS</span>
          <span className={HUD_VALUE}>OPEN</span>
        </button>
        {/* Cognition trace: HAL + committee + broker + human decision timeline. */}
        <button
          type="button"
          onClick={toggleCognition}
          data-tauri-drag-region="false"
          title="See HAL's whole thought process — reasoning, committee, broker, and your own actions on one timeline."
          className={cn(HUD_BTN, HUD_BTN_RED)}
        >
          <span className={cn(HUD_LABEL, "text-hal-red")}>MIND</span>
          <span className={HUD_VALUE}>OPEN</span>
        </button>
        {/* Order-gate toggle: manual (stage + confirm) vs autopilot (HAL fires). */}
        <button
          type="button"
          onClick={() => setTradeMode(autopilot ? "confirm" : "autopilot")}
          data-tauri-drag-region="false"
          title={
            autopilot
              ? "AUTOPILOT — HAL places orders without asking. Click for manual."
              : "MANUAL — HAL stages orders for your confirmation. Click to arm autopilot."
          }
          className={cn(HUD_BTN, autopilot ? HUD_BTN_ACTIVE : HUD_BTN_RED)}
        >
          <span className={cn(HUD_LABEL, autopilot ? "text-hal-amber" : "text-hal-red")}>
            TRADER
          </span>
          <span className={HUD_VALUE}>{autopilot ? "AUTOPILOT" : "MANUAL"}</span>
        </button>
        {/* Risk circuit breaker: ARMED normally; HALTED (clickable to reset)
            once the daily-loss kill switch latches and blocks new entries. */}
        <button
          type="button"
          onClick={() => {
            if (killed && window.confirm(
              `${risk?.kill_reason || "Daily-loss kill switch tripped."}\n\nClear the halt and allow new entries again?`,
            )) resetKillSwitch();
          }}
          data-tauri-drag-region="false"
          title={
            killed
              ? `HALTED — ${risk?.kill_reason}. Click to clear and re-allow entries.`
              : `Risk breakers armed. ${risk?.orders_last_min ?? 0} order(s) in the last minute.`
          }
          className={cn(HUD_BTN, killed ? HUD_BTN_ACTIVE : HUD_BTN_RED)}
        >
          <span className={cn(HUD_LABEL, killed ? "text-hal-amber" : "text-hal-red")}>
            RISK
          </span>
          <span className={HUD_VALUE}>{killed ? "HALTED" : "ARMED"}</span>
        </button>
        <button
          type="button"
          onClick={toggleTradeIdeas}
          data-tauri-drag-region="false"
          className={cn(HUD_BTN, HUD_BTN_AMBER)}
        >
          <span className={cn(HUD_LABEL, "text-hal-amber")}>IDEAS</span>
          <span className={HUD_VALUE}>OPEN</span>
        </button>
        <button
          type="button"
          onClick={toggleMcp}
          data-tauri-drag-region="false"
          className={cn(HUD_BTN, HUD_BTN_RED)}
        >
          <span className={cn(HUD_LABEL, "text-hal-red")}>MCP</span>
          <span className={HUD_VALUE}>OPEN</span>
        </button>
      </div>
    </header>
  );
}
