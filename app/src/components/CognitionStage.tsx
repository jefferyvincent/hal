// "Mind" — a full-screen view of HAL's whole decision process, laid out as a 3D
// BRAIN STEM: a central glowing cord runs top→bottom (chronological), and each
// telemetry event branches off it left/right as a floating, perspective-tilted
// card in its actor's colour (Human / HAL / Committee / Broker / Risk). A pulse
// travels down the cord carrying the question from one actor to the next. While
// the committee is convened, a live roster shows every desk member's verdict and
// status, and a progress bar fills toward the final call. Opened by the HUD MIND
// button. Reads the same telemetry stream as the rest of the app.

import { useEffect, useMemo, useRef, useState } from "react";
import { useConnection } from "@/stores/connection";
import { useUi } from "@/stores/ui";
import type { TelemetryEvent } from "@/types";
import { cn } from "@/lib/cn";

const LANES = ["human", "hal", "committee", "broker", "risk"] as const;
type Lane = (typeof LANES)[number];

const META: Record<Lane, { label: string; color: string }> = {
  human: { label: "Human", color: "#e6e6e6" },
  hal: { label: "HAL", color: "#ffb300" },
  committee: { label: "Committee", color: "#4aa8ff" },
  broker: { label: "Broker", color: "#26a69a" },
  risk: { label: "Risk", color: "#ef5350" },
};

// Brain-stem geometry: a central cord at SPINE_X with cards alternating L/R.
const CARD_W = 240;
const CARD_H = 86;
const Y_TOP = 64;
const Y_STEP = 118;
const GAP = 50; // cord → card inner edge
const MARGIN = 64; // card outer edge → plane edge
const SPINE_X = GAP + CARD_W + MARGIN;
const PLANE_W = SPINE_X * 2;
const MAX_CARDS = 22;
const PULSE_TAIL = 6;

// The fixed committee roster (in desk order) → the telemetry step that fills it.
const ROSTER: { key: string; label: string }[] = [
  { key: "analyst.vol", label: "Vol analyst" },
  { key: "analyst.setup", label: "Setup analyst" },
  { key: "analyst.catalyst", label: "Catalyst analyst" },
  { key: "consensus", label: "Consensus" },
  { key: "debate.bull", label: "Bull researcher" },
  { key: "debate.bear", label: "Bear researcher" },
  { key: "judge", label: "Head trader" },
  { key: "rules_gate", label: "Rules gate" },
  { key: "score", label: "Verdict" },
];

function laneOf(source?: string): Lane {
  return (LANES as readonly string[]).includes(source ?? "") ? (source as Lane) : "hal";
}
function fmtTime(ts?: number): string {
  return ts ? new Date(ts).toLocaleTimeString(undefined, { hour12: false }) : "";
}
// The summary half of a committee event's input ("AVGO · vol: bullish (40%)").
function verdictOf(t: TelemetryEvent): string {
  const parts = (t.input || "").split("·");
  return (parts.length > 1 ? parts.slice(1).join("·") : t.input || t.tool).trim();
}

export default function CognitionStage() {
  const open = useUi((s) => s.cognitionOpen);
  const toggle = useUi((s) => s.toggleCognition);
  const clear = useConnection((s) => s.clearTelemetry);
  const telemetry = useConnection((s) => s.telemetry);
  const mode = useConnection((s) => s.mode);
  const committee = useConnection((s) => s.committeeStatus);
  const scrollRef = useRef<HTMLDivElement>(null);

  const busy = mode === "processing" || mode === "speaking";

  // Zoom-to-card focus (full detail), wheel / +− / Esc to zoom out.
  const [focus, setFocus] = useState<TelemetryEvent | null>(null);
  const [zoom, setZoom] = useState(1);
  useEffect(() => {
    if (!focus) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setFocus(null);
      if (e.key === "+" || e.key === "=") setZoom((z) => Math.min(2.6, z + 0.2));
      if (e.key === "-") setZoom((z) => Math.max(0.7, z - 0.2));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [focus]);
  useEffect(() => {
    if (!open) setFocus(null);
  }, [open]);

  // Elapsed clock while the committee runs.
  const [nowTs, setNowTs] = useState(() => Date.now());
  useEffect(() => {
    if (!committee) return;
    const id = window.setInterval(() => setNowTs(Date.now()), 250);
    return () => window.clearInterval(id);
  }, [committee]);
  const elapsed = committee ? Math.max(0, (nowTs - committee.startedAt) / 1000) : 0;
  const pct = Math.round((committee?.fraction ?? 0) * 100);

  // Position the most-recent events down the brain stem.
  const nodes = useMemo(() => {
    const recent = telemetry.slice(-MAX_CARDS);
    return recent.map((t, i) => {
      const lane = laneOf(t.source);
      const isQuestion = t.tool === "human.question";
      const side = i % 2 === 0 ? -1 : 1; // alternate left / right off the cord
      const top = Y_TOP + i * Y_STEP;
      const cy = top + CARD_H / 2;
      const left = side < 0 ? SPINE_X - GAP - CARD_W : SPINE_X + GAP;
      const innerX = side < 0 ? left + CARD_W : left;
      return { t, lane, isQuestion, side, top, cy, left, innerX,
               color: isQuestion ? "#dff0ff" : META[lane].color };
    });
  }, [telemetry]);

  const planeH = Y_TOP + Math.max(1, nodes.length) * Y_STEP + 70;
  const spineTop = Y_TOP - 8;
  const spineBot = nodes.length ? nodes[nodes.length - 1].cy + 24 : planeH;
  const spinePath = `M ${SPINE_X} ${spineTop} L ${SPINE_X} ${spineBot}`;

  // Branch conduits from the cord out to each card.
  const branches = useMemo(
    () =>
      nodes.map((n, i) => {
        const bow = n.side < 0 ? -26 : 26;
        return {
          id: `branch-${i}`,
          color: n.color,
          d: `M ${SPINE_X} ${n.cy} C ${SPINE_X + bow} ${n.cy}, ${n.innerX - bow} ${n.cy}, ${n.innerX} ${n.cy}`,
          pulse: n.isQuestion || i >= nodes.length - 1 - PULSE_TAIL,
        };
      }),
    [nodes],
  );

  // Follow the newest event (cord grows downward).
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [nodes.length, open]);

  // Committee roster for the current run (events since the last question).
  const roster = useMemo(() => {
    let start = 0;
    for (let i = telemetry.length - 1; i >= 0; i--) {
      if (telemetry[i].tool === "human.question") {
        start = i;
        break;
      }
    }
    const byKey: Record<string, TelemetryEvent> = {};
    for (const t of telemetry.slice(start)) {
      if (t.source === "committee") byKey[(t.tool || "").replace(/^committee\./, "")] = t;
    }
    return ROSTER.map((r) => ({ ...r, ev: byKey[r.key] || null }));
  }, [telemetry]);
  const committeeShown = !!committee || roster.some((r) => r.ev);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 flex flex-col bg-[#05070b] text-hal-text">
      <div
        className="pointer-events-none absolute inset-0 opacity-50"
        style={{
          background:
            "radial-gradient(1100px 700px at 50% 8%, rgba(40,90,140,0.16), transparent 70%)," +
            "radial-gradient(800px 500px at 50% 100%, rgba(120,30,30,0.12), transparent 70%)",
        }}
      />
      <style>{cognitionCss}</style>

      {/* Header. */}
      <header className="relative z-10 flex items-center justify-between border-b border-white/10 px-7 py-4">
        <div className="flex items-center gap-3">
          <span className="text-[11px] uppercase tracking-[6px] text-[#7fb2ff]">HAL · Cognition</span>
          <span className="text-[10px] tracking-[2px] text-hal-text-dim">whole decision process</span>
        </div>
        <div className="flex items-center gap-5 text-[9px] uppercase tracking-[2px]">
          <button type="button" onClick={clear} className="text-hal-text-dim hover:text-white">Clear</button>
          <button type="button" onClick={toggle} className="text-hal-text-dim hover:text-white">Close ✕</button>
        </div>
      </header>

      {/* Lane legend. */}
      <div className="relative z-10 flex flex-wrap gap-4 px-7 py-2">
        {LANES.map((l) => (
          <span key={l} className="flex items-center gap-1.5 text-[9px] uppercase tracking-[2px]">
            <span className="h-2 w-2 rounded-full" style={{ background: META[l].color, boxShadow: `0 0 8px ${META[l].color}` }} />
            <span style={{ color: META[l].color }}>{META[l].label}</span>
          </span>
        ))}
      </div>

      {/* Committee progress bar. */}
      {committee ? (
        <div className="relative z-10 px-7 pb-2">
          <div className="mb-1 flex items-center justify-between text-[10px] uppercase tracking-[2px]">
            <span style={{ color: META.committee.color }}>
              Committee · {committee.symbol} {committee.label ? `· ${committee.label}` : ""}
            </span>
            <span className="tabular-nums text-hal-text-dim">{pct}% · {elapsed.toFixed(0)}s</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full rounded-full transition-[width] duration-500 ease-out"
              style={{ width: `${pct}%`, background: `linear-gradient(90deg, ${META.committee.color}, #9fe4ff)`, boxShadow: `0 0 12px ${META.committee.color}` }}
            />
          </div>
        </div>
      ) : null}

      {/* The brain stem. */}
      <div ref={scrollRef} className="relative z-10 flex-1 overflow-y-auto overflow-x-hidden">
        {nodes.length === 0 ? (
          <div className="flex h-full items-center justify-center text-[12px] text-hal-text-dim">
            (no cognition yet — ask HAL for a trade idea, run the committee, or place an order)
          </div>
        ) : (
          <div className="relative mx-auto my-3" style={{ width: PLANE_W, height: planeH, perspective: "1500px" }}>
            <svg className="absolute inset-0" width={PLANE_W} height={planeH} style={{ overflow: "visible" }}>
              {/* Central cord (the stem). */}
              <path id="cog-spine" d={spinePath} fill="none" stroke="#3b6ea5" strokeOpacity={0.4} strokeWidth={9} strokeLinecap="round" />
              <path d={spinePath} fill="none" stroke="#8fd0ff" strokeWidth={2.5} strokeLinecap="round" style={{ filter: "drop-shadow(0 0 6px #4aa8ff)" }} />
              {/* Pulses flowing down the cord. */}
              {[0, 1].map((k) => (
                <circle key={k} r={4.5} fill="#eaf6ff" style={{ filter: "drop-shadow(0 0 7px #7fc8ff)" }}>
                  <animateMotion dur="2.6s" begin={`${k * 1.3}s`} repeatCount="indefinite" keyPoints="0;1" keyTimes="0;1" calcMode="linear">
                    <mpath href="#cog-spine" />
                  </animateMotion>
                </circle>
              ))}
              {/* Branch conduits. */}
              {branches.map((b) => (
                <g key={b.id}>
                  <path d={b.d} fill="none" stroke={b.color} strokeOpacity={0.35} strokeWidth={1.6} />
                  <path d={b.d} fill="none" stroke={b.color} strokeWidth={1.6} strokeOpacity={0.9} strokeDasharray="5 12" className="cog-flow" style={{ filter: `drop-shadow(0 0 3px ${b.color})` }} />
                  {b.pulse ? (
                    <circle r={3} fill="#ffffff" style={{ filter: `drop-shadow(0 0 5px ${b.color})` }}>
                      <animateMotion dur="1.5s" repeatCount="indefinite" keyPoints="0;1" keyTimes="0;1" calcMode="linear">
                        <mpath href={`#${b.id}`} />
                      </animateMotion>
                    </circle>
                  ) : null}
                </g>
              ))}
            </svg>

            {/* Cards branching off the stem. */}
            {nodes.map((n, i) => {
              const newest = i === nodes.length - 1;
              const depth = Math.max(-70, -(nodes.length - 1 - i) * 5);
              return (
                <article
                  key={i}
                  onClick={() => {
                    setZoom(1);
                    setFocus(n.t);
                  }}
                  title="Click to zoom in"
                  className={cn("cog-card absolute cursor-pointer", newest && "cog-card-new", newest && busy && "cog-card-busy")}
                  style={{
                    left: n.left,
                    top: n.top,
                    width: CARD_W,
                    height: CARD_H,
                    transform: `translateZ(${depth}px) rotateY(${n.side < 0 ? 13 : -13}deg)`,
                    borderColor: `${n.color}66`,
                    boxShadow: `0 0 0 1px ${n.color}22, 0 8px 26px rgba(0,0,0,0.55), 0 0 20px ${n.color}33`,
                    background: `linear-gradient(160deg, ${n.color}1c, rgba(8,12,18,0.88))`,
                    animationDelay: `${(i % 6) * 0.25}s`,
                  }}
                >
                  <div className="flex items-center gap-2">
                    <span className="rounded-sm px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-[1px]" style={{ color: n.color, border: `1px solid ${n.color}66` }}>
                      {n.isQuestion ? "? Question" : META[n.lane].label}
                    </span>
                    <span className="text-[8px] tabular-nums text-hal-text-dim">{fmtTime(n.t.ts)}</span>
                    {n.t.status === "error" ? <span className="ml-auto text-[8px] uppercase text-hal-amber-bright">error</span> : null}
                  </div>
                  {n.isQuestion ? (
                    <div className="mt-1 line-clamp-2 text-[11px] font-medium leading-snug text-white">
                      {n.t.output || n.t.input || "(question)"}
                    </div>
                  ) : (
                    <>
                      <div className="mt-1 truncate text-[10.5px] uppercase tracking-[1.5px]" style={{ color: n.color }}>{n.t.tool}</div>
                      <div className="mt-0.5 line-clamp-2 text-[9.5px] leading-snug text-hal-text-dim">{n.t.input || n.t.output || ""}</div>
                    </>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </div>

      {/* Committee roster: every desk member, their verdict, and status. Pinned
          to the viewport (outside the scrolling stem) so it stays in view. */}
      {committeeShown ? (
        <aside className="absolute right-4 top-[150px] z-20 w-[236px] rounded-lg border border-[#4aa8ff44] bg-[rgba(8,14,22,0.94)] p-3 shadow-[0_0_30px_rgba(0,0,0,0.6)] backdrop-blur-md">
          <div className="mb-2 text-[10px] uppercase tracking-[3px]" style={{ color: META.committee.color }}>Committee desk</div>
          <div className="flex flex-col gap-1.5">
            {roster.map((r) => {
              const done = !!r.ev;
              const active = !done && !!committee && committee.label === r.label;
              return (
                <div key={r.key} className="flex items-start gap-2">
                  <span
                    className={cn("mt-1 h-1.5 w-1.5 shrink-0 rounded-full", active && "cog-dot-active")}
                    style={{ background: done ? META.committee.color : active ? "#9fe4ff" : "#3a4150", boxShadow: done ? `0 0 6px ${META.committee.color}` : undefined }}
                  />
                  <div className="min-w-0">
                    <div className={cn("text-[9.5px] uppercase tracking-[1px]", done ? "text-hal-text" : "text-hal-text-dim")}>{r.label}</div>
                    <div className="truncate text-[9px] text-hal-text-dim">{done ? verdictOf(r.ev!) : active ? "working…" : "pending"}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </aside>
      ) : null}

      <footer className="relative z-10 border-t border-white/10 px-7 py-2 text-[9px] tracking-[1px] text-hal-text-dim">
        Most recent {Math.min(MAX_CARDS, telemetry.length)} of {telemetry.length} events · the cord is the decision flow, cards branch off it · click a card to zoom in.
      </footer>

      {focus ? <FocusCard event={focus} zoom={zoom} setZoom={setZoom} onClose={() => setFocus(null)} /> : null}
    </div>
  );
}

function FocusCard({ event, zoom, setZoom, onClose }: { event: TelemetryEvent; zoom: number; setZoom: (fn: (z: number) => number) => void; onClose: () => void }) {
  const lane = laneOf(event.source);
  const isQuestion = event.tool === "human.question";
  const color = isQuestion ? "#dff0ff" : META[lane].color;
  return (
    <div
      className="absolute inset-0 z-20 flex items-center justify-center bg-black/70 backdrop-blur-[2px]"
      onClick={onClose}
      onWheel={(e) => setZoom((z) => Math.min(2.6, Math.max(0.7, z - Math.sign(e.deltaY) * 0.12)))}
    >
      <article
        onClick={(e) => e.stopPropagation()}
        className="cog-focus relative flex max-h-[80vh] w-[560px] max-w-[88vw] flex-col overflow-hidden rounded-xl"
        style={{ transform: `scale(${zoom})`, borderTop: `2px solid ${color}`, boxShadow: `0 0 0 1px ${color}44, 0 24px 80px rgba(0,0,0,0.7), 0 0 60px ${color}40`, background: `linear-gradient(160deg, ${color}1f, rgba(8,12,18,0.97))` }}
      >
        <header className="flex items-center gap-3 border-b border-white/10 px-4 py-3">
          <span className="rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-[1.5px]" style={{ color, border: `1px solid ${color}66` }}>
            {isQuestion ? "? Question" : META[lane].label}
          </span>
          <span className="text-[11px] uppercase tracking-[2px]" style={{ color }}>{event.tool}</span>
          <span className="text-[10px] tabular-nums text-hal-text-dim">{fmtTime(event.ts)}</span>
          <div className="ml-auto flex items-center gap-1">
            <ZoomBtn label="−" onClick={() => setZoom((z) => Math.max(0.7, z - 0.2))} />
            <span className="w-10 text-center text-[10px] tabular-nums text-hal-text-dim">{Math.round(zoom * 100)}%</span>
            <ZoomBtn label="+" onClick={() => setZoom((z) => Math.min(2.6, z + 0.2))} />
            <button type="button" onClick={onClose} className="ml-2 text-[10px] uppercase tracking-[2px] text-hal-text-dim hover:text-white">✕</button>
          </div>
        </header>
        <div className="flex flex-col gap-2 overflow-y-auto p-4 font-mono">
          {event.input ? (
            <>
              <div className="text-[8px] uppercase tracking-[2px] text-hal-text-dim">Input</div>
              <pre className="select-text whitespace-pre-wrap break-words border-l border-white/15 bg-black/40 px-3 py-2 text-[11px] leading-snug text-hal-text-dim">{event.input}</pre>
            </>
          ) : null}
          {event.output ? (
            <>
              <div className="mt-1 text-[8px] uppercase tracking-[2px] text-hal-text-dim">Output</div>
              <pre className="select-text whitespace-pre-wrap break-words bg-black/40 px-3 py-2 text-[12px] leading-relaxed text-hal-text">{event.output}</pre>
            </>
          ) : null}
          {!event.input && !event.output ? <div className="text-[11px] text-hal-text-dim">(no detail captured for this step)</div> : null}
        </div>
      </article>
    </div>
  );
}

function ZoomBtn({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="h-5 w-5 rounded border border-white/20 text-[12px] leading-none text-hal-text-dim hover:border-white/50 hover:text-white">
      {label}
    </button>
  );
}

const cognitionCss = `
@keyframes cogFlow { to { stroke-dashoffset: -34; } }
.cog-flow { animation: cogFlow 1.1s linear infinite; }
.cog-card {
  border-width: 1px; border-style: solid; border-radius: 10px; padding: 7px 10px;
  backdrop-filter: blur(3px); transform-style: preserve-3d; transition: box-shadow .3s ease;
}
.cog-card-new { animation: cogPulse 1.6s ease-out; }
@keyframes cogPulse { 0% { box-shadow: 0 0 0 1px #fff8, 0 0 40px #fff6; } 100% { box-shadow: 0 8px 30px rgba(0,0,0,0.55); } }
.cog-card-busy { animation: cogBusy 1.3s ease-in-out infinite; }
@keyframes cogBusy {
  0%,100% { box-shadow: 0 0 0 1px #ffffff22, 0 8px 30px rgba(0,0,0,0.55), 0 0 18px #ffffff22; }
  50%     { box-shadow: 0 0 0 1px #ffffff66, 0 8px 30px rgba(0,0,0,0.55), 0 0 34px #ffffff66; }
}
.cog-dot-active { animation: cogDot 1s ease-in-out infinite; }
@keyframes cogDot { 0%,100% { opacity: .4; } 50% { opacity: 1; } }
.cog-focus { animation: cogZoomIn .22s ease-out; transition: transform .12s ease-out; transform-origin: center; }
@keyframes cogZoomIn { from { opacity: 0; transform: scale(.7); } to { opacity: 1; } }
`;
