import { useEffect, useState } from "react";
import { useConnection } from "@/stores/connection";
import { useUi } from "@/stores/ui";

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
      </div>
    </header>
  );
}
