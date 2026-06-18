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

export default function Hud() {
  const [uptime, setUptime] = useState("00:00:00");
  const stateLabel = useConnection((s) => s.stateLabel);
  const subline = useConnection((s) => s.subline);
  const toggleConv = useUi((s) => s.toggleConversations);
  const toggleMcp = useUi((s) => s.toggleMcp);
  const toggleSubscriptions = useUi((s) => s.toggleSubscriptions);
  const togglePositions = useUi((s) => s.togglePositions);
  const tradeMode = useConnection((s) => s.tradeMode);
  const setTradeMode = useConnection((s) => s.setTradeMode);
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
        <button
          type="button"
          onClick={toggleConv}
          data-tauri-drag-region="false"
          className="flex flex-col gap-[3px] border border-hal-red/35 bg-hal-red/[0.06] px-3 py-[5px] uppercase tracking-[4px] transition-colors hover:border-hal-red hover:bg-hal-red/20 hover:shadow-[0_0_14px_rgba(255,30,30,0.4)]"
        >
          <span className="text-[9px] text-hal-red">CHATS</span>
          <span className="font-bold text-white">OPEN</span>
        </button>
        <button
          type="button"
          onClick={toggleSubscriptions}
          data-tauri-drag-region="false"
          className="flex flex-col gap-[3px] border border-hal-red/35 bg-hal-red/[0.06] px-3 py-[5px] uppercase tracking-[4px] transition-colors hover:border-hal-red hover:bg-hal-red/20 hover:shadow-[0_0_14px_rgba(255,30,30,0.4)]"
        >
          <span className="text-[9px] text-hal-red">WATCHES</span>
          <span className="font-bold text-white">OPEN</span>
        </button>
        <button
          type="button"
          onClick={togglePositions}
          data-tauri-drag-region="false"
          className="flex flex-col gap-[3px] border border-hal-red/35 bg-hal-red/[0.06] px-3 py-[5px] uppercase tracking-[4px] transition-colors hover:border-hal-red hover:bg-hal-red/20 hover:shadow-[0_0_14px_rgba(255,30,30,0.4)]"
        >
          <span className="text-[9px] text-hal-red">POSITIONS</span>
          <span className="font-bold text-white">OPEN</span>
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
          className={cn(
            "flex flex-col gap-[3px] border px-3 py-[5px] uppercase tracking-[4px] transition-colors",
            autopilot
              ? "border-hal-amber bg-hal-amber/20 shadow-[0_0_14px_rgba(255,176,0,0.5)] hover:bg-hal-amber/30"
              : "border-hal-red/35 bg-hal-red/[0.06] hover:border-hal-red hover:bg-hal-red/20 hover:shadow-[0_0_14px_rgba(255,30,30,0.4)]",
          )}
        >
          <span className={cn("text-[9px]", autopilot ? "text-hal-amber" : "text-hal-red")}>
            TRADER
          </span>
          <span className="font-bold text-white">{autopilot ? "AUTOPILOT" : "MANUAL"}</span>
        </button>
        <button
          type="button"
          onClick={toggleTradeIdeas}
          data-tauri-drag-region="false"
          className="flex flex-col gap-[3px] border border-hal-amber/35 bg-hal-amber/[0.06] px-3 py-[5px] uppercase tracking-[4px] transition-colors hover:border-hal-amber hover:bg-hal-amber/20 hover:shadow-[0_0_14px_rgba(255,176,0,0.4)]"
        >
          <span className="text-[9px] text-hal-amber">IDEAS</span>
          <span className="font-bold text-white">OPEN</span>
        </button>
        <button
          type="button"
          onClick={toggleMcp}
          data-tauri-drag-region="false"
          className="flex flex-col gap-[3px] border border-hal-red/35 bg-hal-red/[0.06] px-3 py-[5px] uppercase tracking-[4px] transition-colors hover:border-hal-red hover:bg-hal-red/20 hover:shadow-[0_0_14px_rgba(255,30,30,0.4)]"
        >
          <span className="text-[9px] text-hal-red">MCP</span>
          <span className="font-bold text-white">OPEN</span>
        </button>
      </div>
    </header>
  );
}
