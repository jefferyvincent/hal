import { useEffect, useState, type ReactNode } from "react";
import { useConnection } from "@/stores/connection";
import { useUi } from "@/stores/ui";
import { useImmersive } from "@/stores/immersive";
import { cn } from "@/lib/cn";
import { HAL_DESIGNATION } from "@/lib/identity";

function formatUptime(ms: number): string {
  const s = Math.floor(ms / 1000);
  const h = String(Math.floor(s / 3600)).padStart(2, "0");
  const m = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  const sec = String(s % 60).padStart(2, "0");
  return `${h}:${m}:${sec}`;
}

const BOOT = Date.now();

// Round icon button, mirroring the AuxBtn aesthetic in Controls.tsx so the HUD
// cluster reads as the same family. Compact (40px) since there are nine of them.
const HUD_ICON_BTN =
  "flex h-10 w-10 items-center justify-center rounded-full border transition-all";
const HUD_ICON_RED =
  "border-hal-red/45 bg-hal-red/[0.08] text-hal-text hover:border-hal-red hover:bg-hal-red/25 hover:text-white hover:shadow-[0_0_14px_rgba(255,30,30,0.45)]";
const HUD_ICON_AMBER =
  "border-hal-amber/45 bg-hal-amber/[0.08] text-hal-amber hover:border-hal-amber hover:bg-hal-amber/25 hover:text-white hover:shadow-[0_0_14px_rgba(255,176,0,0.45)]";
// Lit-up state for toggles that are "on" (autopilot armed, voice muted, halted).
const HUD_ICON_ACTIVE =
  "border-hal-amber bg-hal-amber/25 text-hal-amber-bright shadow-[0_0_14px_rgba(255,176,0,0.55)] hover:bg-hal-amber/35";
const SVG_ICON = "h-[18px] w-[18px]";

function HudBtn({
  onClick,
  title,
  active,
  variant = "red",
  children,
}: {
  onClick: () => void;
  title: string;
  active?: boolean;
  variant?: "red" | "amber";
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-tauri-drag-region="false"
      title={title}
      className={cn(
        HUD_ICON_BTN,
        active ? HUD_ICON_ACTIVE : variant === "amber" ? HUD_ICON_AMBER : HUD_ICON_RED,
      )}
    >
      {children}
    </button>
  );
}

// Shared SVG attrs for the line-style icons below.
const strokeProps = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

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
  const halListen = useConnection((s) => s.halListen);
  const toggleHalListen = useConnection((s) => s.toggleHalListen);
  const quiet = useConnection((s) => s.quiet);
  const toggleQuiet = useConnection((s) => s.toggleQuiet);
  const autopilot = tradeMode === "autopilot";

  // The HUD controls rest collapsed — just the chevron handle on the right.
  // Tapping it fans the nine icon buttons out to the left, like the mic cluster.
  const [expanded, setExpanded] = useState(false);

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
          <div className="text-hal-text">{HAL_DESIGNATION}</div>
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

        {/* Icon cluster: fans in-flow to the left of the chevron when expanded,
            and tucks away entirely (only the chevron remains) when collapsed. */}
        <div className="flex items-center gap-2">
          {expanded ? (
            <div className="flex items-center gap-2">
              {/* Mute HAL's voice. Speech still streams + drives the eye/state,
                  just silenced. Amber when muted = active override. */}
              <HudBtn
                onClick={toggleMute}
                active={muted}
                title={
                  muted
                    ? "VOICE — HAL is MUTED. Click to unmute."
                    : "VOICE — HAL's voice is on. Click to mute."
                }
              >
                <svg className={SVG_ICON} {...strokeProps}>
                  <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                  {muted ? (
                    <>
                      <line x1="23" y1="9" x2="17" y2="15" />
                      <line x1="17" y1="9" x2="23" y2="15" />
                    </>
                  ) : (
                    <>
                      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
                      <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
                    </>
                  )}
                </svg>
              </HudBtn>

              {/* Quiet mode (do-not-disturb). Holds every proactive spoken alert
                  (news / earnings / price / managed-exit) AND stops HAL
                  volunteering trade ideas, until lifted. Amber when engaged =
                  active override. Distinct from VOICE mute, which only silences
                  TTS while alerts still fire. */}
              <HudBtn
                onClick={toggleQuiet}
                active={quiet}
                title={
                  quiet
                    ? "QUIET — do-not-disturb is ON. HAL is holding all alerts and ideas. Click to resume."
                    : "QUIET — alerts and ideas are live. Click for do-not-disturb (hold all alerts + suggestions)."
                }
              >
                <svg className={SVG_ICON} {...strokeProps}>
                  <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
                  <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                  {quiet ? <line x1="3" y1="3" x2="21" y2="21" /> : null}
                </svg>
              </HudBtn>

              {/* Privacy / stop-listening. HAL opens the mic after asking a
                  question (and stays open hands-free in immersive); this latches
                  that off. Amber when privacy is engaged = active override. */}
              <HudBtn
                onClick={toggleHalListen}
                active={!halListen}
                title={
                  halListen
                    ? "PRIVACY — HAL listens for your reply after asking. Click to stop listening."
                    : "PRIVACY — HAL won't open the mic. Click to allow listening."
                }
              >
                <svg className={SVG_ICON} {...strokeProps}>
                  <rect x="9" y="3" width="6" height="11" rx="3" />
                  <path d="M5 11a7 7 0 0 0 14 0" />
                  <line x1="12" y1="18" x2="12" y2="22" />
                  {!halListen ? <line x1="3" y1="3" x2="21" y2="21" /> : null}
                </svg>
              </HudBtn>

              {/* Chats / conversation transcript. */}
              <HudBtn onClick={toggleConv} title="CHATS — open conversations">
                <svg className={SVG_ICON} {...strokeProps}>
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
              </HudBtn>

              {/* Watches — the news/symbol watchlist subscriptions. */}
              <HudBtn onClick={toggleSubscriptions} title="WATCHES — open watchlist">
                <svg className={SVG_ICON} {...strokeProps}>
                  <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              </HudBtn>

              {/* Positions — open holdings. */}
              <HudBtn onClick={togglePositions} title="POSITIONS — open positions">
                <svg className={SVG_ICON} {...strokeProps}>
                  <line x1="6" y1="20" x2="6" y2="14" />
                  <line x1="12" y1="20" x2="12" y2="4" />
                  <line x1="18" y1="20" x2="18" y2="10" />
                </svg>
              </HudBtn>

              {/* Cognition trace: HAL + committee + broker + human timeline. */}
              <HudBtn
                onClick={toggleCognition}
                title="MIND — HAL's whole thought process: reasoning, committee, broker, and your own actions on one timeline."
              >
                <svg className={SVG_ICON} {...strokeProps}>
                  <circle cx="18" cy="5" r="3" />
                  <circle cx="6" cy="12" r="3" />
                  <circle cx="18" cy="19" r="3" />
                  <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
                  <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
                </svg>
              </HudBtn>

              {/* Order-gate toggle: manual (stage + confirm) vs autopilot. */}
              <HudBtn
                onClick={() => setTradeMode(autopilot ? "confirm" : "autopilot")}
                active={autopilot}
                title={
                  autopilot
                    ? "TRADER — AUTOPILOT: HAL places orders without asking. Click for manual."
                    : "TRADER — MANUAL: HAL stages orders for your confirmation. Click to arm autopilot."
                }
              >
                <svg className={SVG_ICON} {...strokeProps}>
                  <rect x="4" y="4" width="16" height="16" rx="2" />
                  <rect x="9" y="9" width="6" height="6" />
                  <line x1="9" y1="1" x2="9" y2="4" />
                  <line x1="15" y1="1" x2="15" y2="4" />
                  <line x1="9" y1="20" x2="9" y2="23" />
                  <line x1="15" y1="20" x2="15" y2="23" />
                  <line x1="20" y1="9" x2="23" y2="9" />
                  <line x1="20" y1="14" x2="23" y2="14" />
                  <line x1="1" y1="9" x2="4" y2="9" />
                  <line x1="1" y1="14" x2="4" y2="14" />
                </svg>
              </HudBtn>

              {/* Risk circuit breaker: ARMED normally; HALTED (clickable to
                  reset) once the daily-loss kill switch latches. */}
              <HudBtn
                onClick={() => {
                  if (killed && window.confirm(
                    `${risk?.kill_reason || "Daily-loss kill switch tripped."}\n\nClear the halt and allow new entries again?`,
                  )) resetKillSwitch();
                }}
                active={killed}
                title={
                  killed
                    ? `RISK — HALTED: ${risk?.kill_reason}. Click to clear and re-allow entries.`
                    : `RISK — armed. ${risk?.orders_last_min ?? 0} order(s) in the last minute.`
                }
              >
                <svg className={SVG_ICON} {...strokeProps}>
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  {killed ? (
                    <>
                      <line x1="12" y1="8" x2="12" y2="12" />
                      <line x1="12" y1="16" x2="12.01" y2="16" />
                    </>
                  ) : (
                    <polyline points="9 12 11 14 15 10" />
                  )}
                </svg>
              </HudBtn>

              {/* Trade ideas (immersive source). */}
              <HudBtn
                onClick={toggleTradeIdeas}
                variant="amber"
                title="IDEAS — open trade ideas"
              >
                <svg className={SVG_ICON} {...strokeProps}>
                  <path d="M9 18h6" />
                  <path d="M10 22h4" />
                  <path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.1h6c0-.8.4-1.6 1-2.1A7 7 0 0 0 12 2z" />
                </svg>
              </HudBtn>

              {/* MCP servers. */}
              <HudBtn onClick={toggleMcp} title="MCP — open MCP servers">
                <svg className={SVG_ICON} {...strokeProps}>
                  <rect x="2" y="2" width="20" height="8" rx="2" />
                  <rect x="2" y="14" width="20" height="8" rx="2" />
                  <line x1="6" y1="6" x2="6.01" y2="6" />
                  <line x1="6" y1="18" x2="6.01" y2="18" />
                </svg>
              </HudBtn>
            </div>
          ) : null}

          {/* Chevron handle — the "0" of the cluster. Points left when
              collapsed ("reveal"), rotates to point right when expanded
              ("close"). Goes amber if the kill switch is tripped so a HALTED
              state still grabs attention even while the cluster is tucked away. */}
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            data-tauri-drag-region="false"
            aria-expanded={expanded}
            title={expanded ? "Hide controls" : "Show controls"}
            className={cn(HUD_ICON_BTN, killed ? HUD_ICON_ACTIVE : HUD_ICON_RED)}
          >
            <svg
              className={cn(SVG_ICON, "transition-transform duration-300", expanded && "rotate-180")}
              {...strokeProps}
            >
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
        </div>
      </div>
    </header>
  );
}
