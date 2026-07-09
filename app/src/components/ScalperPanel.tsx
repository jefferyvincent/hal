import { useEffect, useState } from "react";
import { useConnection } from "@/stores/connection";
import { useUi } from "@/stores/ui";
import { cn } from "@/lib/cn";

const REFRESH_MS = 5000;

function money(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

// Terminal statuses the loop has stopped on → shown as a badge colour.
const STOPPED = new Set(["target_hit", "floor_hit", "stopped", "error"]);

// The autonomous scalper: arm it with capital + a dollar target and it trades
// the committee's verdicts in autopilot until it hits the target or the floor.
// This panel is the live cockpit — status, P&L vs target, and a Stop control.
export default function ScalperPanel() {
  const open = useUi((s) => s.scalperOpen);
  const toggle = useUi((s) => s.toggleScalper);
  const status = useConnection((s) => s.scalperStatus);
  const ready = useConnection((s) => s.brokerReady);
  const paper = useConnection((s) => s.brokerPaper);
  const mode = useConnection((s) => s.tradeMode);
  const refresh = useConnection((s) => s.refreshScalper);
  const startScalper = useConnection((s) => s.startScalper);
  const stopScalper = useConnection((s) => s.stopScalper);
  const setTradeMode = useConnection((s) => s.setTradeMode);

  // Start-form inputs (used only when no session is running).
  const [capital, setCapital] = useState("5000");
  const [target, setTarget] = useState("250");
  const [loss, setLoss] = useState("");
  const [period, setPeriod] = useState<"day" | "week">("day");
  const [confirmStop, setConfirmStop] = useState(false);

  // Poll while open; refresh immediately on open.
  useEffect(() => {
    if (!open) return;
    refresh();
    const id = window.setInterval(refresh, REFRESH_MS);
    return () => window.clearInterval(id);
  }, [open, refresh]);

  useEffect(() => {
    if (!status) setConfirmStop(false);
  }, [status]);

  if (!open) return null;

  const autopilot = mode === "autopilot";
  const running = !!status && !STOPPED.has(status.status);

  const onStart = () => {
    const cap = parseFloat(capital);
    const tgt = parseFloat(target);
    if (!(cap > 0) || !(tgt > 0)) return;
    const lossNum = parseFloat(loss);
    startScalper({
      capital: cap,
      profit_target: tgt,
      loss_limit: Number.isFinite(lossNum) && lossNum > 0 ? lossNum : undefined,
      period,
    });
  };

  return (
    <div
      className="fixed inset-0 z-40 flex items-start justify-center bg-black/60 backdrop-blur-sm"
      onClick={toggle}
    >
      <aside
        onClick={(e) => e.stopPropagation()}
        className={cn(
          "mt-[56px] flex max-h-[calc(100vh-92px)] w-[min(680px,94vw)] flex-col font-mono",
          "border border-hal-red/25 bg-[rgba(8,8,11,0.96)] shadow-[0_0_40px_rgba(0,0,0,0.7)]",
        )}
      >
        <header className="flex items-center justify-between border-b border-hal-red/20 bg-hal-red/[0.04] px-3 py-2.5 text-[9px] uppercase tracking-[4px] text-hal-red">
          <span>Scalper · Robo Trader</span>
          <div className="flex items-center gap-3">
            <span
              className={cn(
                "border px-1.5 py-0.5 text-[8px] tracking-[2px]",
                paper
                  ? "border-emerald-500/40 text-emerald-400"
                  : "border-hal-red/60 text-hal-red-glow",
              )}
            >
              {paper ? "PAPER" : "LIVE"}
            </span>
            <span className="text-[8px] tracking-[2px] text-hal-text-dim">
              {autopilot ? "AUTOPILOT" : "CONFIRM"}
            </span>
            <button
              type="button"
              onClick={toggle}
              className="text-[9px] uppercase tracking-[2px] text-hal-text-dim hover:text-hal-red-glow"
            >
              Close
            </button>
          </div>
        </header>

        {!ready ? (
          <div className="px-3 py-6 text-center text-[12px] text-hal-text-dim">
            Alpaca isn't configured. Set ALPACA_API_KEY and ALPACA_SECRET_KEY in
            .env to run the scalper.
          </div>
        ) : running && status ? (
          <RunningView
            status={status}
            confirmStop={confirmStop}
            setConfirmStop={setConfirmStop}
            stopScalper={stopScalper}
          />
        ) : (
          <StartView
            status={status}
            autopilot={autopilot}
            capital={capital}
            setCapital={setCapital}
            target={target}
            setTarget={setTarget}
            loss={loss}
            setLoss={setLoss}
            period={period}
            setPeriod={setPeriod}
            onStart={onStart}
            setTradeMode={setTradeMode}
          />
        )}

        <footer className="border-t border-hal-red/15 px-3 py-2 text-[8px] uppercase tracking-[2px] text-hal-text-dim">
          Auto-trades committee verdicts in autopilot. Halts at target or floor.
        </footer>
      </aside>
    </div>
  );
}

function RunningView({
  status,
  confirmStop,
  setConfirmStop,
  stopScalper,
}: {
  status: import("@/types").ScalperStatus;
  confirmStop: boolean;
  setConfirmStop: (v: boolean) => void;
  stopScalper: (flatten: boolean) => void;
}) {
  const pnl = status.total_pnl;
  const up = pnl >= 0;
  // Progress toward the target (0..1). Negative P&L shows an empty bar.
  const frac = Math.max(0, Math.min(1, pnl / (status.profit_target || 1)));
  const positions = Object.entries(status.open_positions);

  return (
    <div className="flex flex-col gap-3 overflow-y-auto px-3 py-3 text-[12px]">
      <div className="flex items-center justify-between">
        <span className="text-[9px] uppercase tracking-[3px] text-hal-text-dim">
          {status.status.replace("_", " ")} · {status.period} · {status.passes} passes
        </span>
        <span className="text-[9px] uppercase tracking-[2px] text-hal-text-dim">
          floor {money(-status.loss_limit)}
        </span>
      </div>

      {/* P&L vs target */}
      <div>
        <div className="mb-1 flex items-baseline justify-between">
          <span
            className={cn(
              "text-[22px] font-bold leading-none",
              up ? "text-emerald-400" : "text-hal-red-glow",
            )}
          >
            {up ? "+" : ""}
            {money(pnl)}
          </span>
          <span className="text-[11px] text-hal-text-dim">
            of {money(status.profit_target)} target
          </span>
        </div>
        <div className="h-2 w-full overflow-hidden border border-hal-red/20 bg-black/40">
          <div
            className={cn("h-full", up ? "bg-emerald-500/60" : "bg-hal-red/40")}
            style={{ width: `${frac * 100}%` }}
          />
        </div>
        <div className="mt-1 flex justify-between text-[10px] text-hal-text-dim">
          <span>realized {money(status.realized_pnl)}</span>
          <span>open {money(status.unrealized_pnl)}</span>
        </div>
      </div>

      {/* Open positions the session owns */}
      <div>
        <div className="mb-1 text-[9px] uppercase tracking-[3px] text-hal-text-dim">
          Holding · {positions.length}
        </div>
        {positions.length === 0 ? (
          <div className="py-2 text-center text-[11px] text-hal-text-dim">
            (nothing open yet)
          </div>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {positions.map(([sym, side]) => (
              <span
                key={sym}
                className={cn(
                  "border px-2 py-1 text-[11px] font-bold uppercase tracking-[1px]",
                  side === "buy"
                    ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-300"
                    : "border-hal-red/50 bg-hal-red/10 text-hal-red-glow",
                )}
              >
                {side === "buy" ? "LONG" : "SHORT"} {sym}
              </span>
            ))}
          </div>
        )}
      </div>

      {status.note ? (
        <div className="border-l-2 border-hal-red/30 pl-2 text-[11px] text-hal-text-dim">
          {status.note}
        </div>
      ) : null}

      {/* Stop controls. With no open positions there's nothing to flatten, so
          skip the keep/flatten choice and just stop. */}
      {confirmStop && positions.length > 0 ? (
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => stopScalper(false)}
            className="flex-1 border border-hal-amber/50 bg-hal-amber/10 px-2 py-2 text-[11px] uppercase tracking-[1px] text-hal-amber hover:bg-hal-amber/20"
          >
            Stop · keep positions
          </button>
          <button
            type="button"
            onClick={() => stopScalper(true)}
            className="flex-1 border border-hal-red/60 bg-hal-red/15 px-2 py-2 text-[11px] uppercase tracking-[1px] text-hal-red-glow hover:bg-hal-red/30"
          >
            Stop · flatten all
          </button>
          <button
            type="button"
            onClick={() => setConfirmStop(false)}
            className="px-2 py-2 text-[11px] uppercase tracking-[1px] text-hal-text-dim hover:text-hal-text"
          >
            ✕
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => (positions.length === 0 ? stopScalper(false) : setConfirmStop(true))}
          className="border border-hal-red/40 px-3 py-2 text-[11px] uppercase tracking-[2px] text-hal-text-dim transition-colors hover:border-hal-red hover:text-hal-red-glow"
        >
          Stop scalper
        </button>
      )}
    </div>
  );
}

function StartView({
  status,
  autopilot,
  capital,
  setCapital,
  target,
  setTarget,
  loss,
  setLoss,
  period,
  setPeriod,
  onStart,
  setTradeMode,
}: {
  status: import("@/types").ScalperStatus | null;
  autopilot: boolean;
  capital: string;
  setCapital: (v: string) => void;
  target: string;
  setTarget: (v: string) => void;
  loss: string;
  setLoss: (v: string) => void;
  period: "day" | "week";
  setPeriod: (v: "day" | "week") => void;
  onStart: () => void;
  setTradeMode: (m: "confirm" | "autopilot") => void;
}) {
  const canStart = autopilot && parseFloat(capital) > 0 && parseFloat(target) > 0;
  return (
    <div className="flex flex-col gap-3 px-3 py-3 text-[12px]">
      {status ? (
        <div className="border-l-2 border-hal-red/30 pl-2 text-[11px] text-hal-text-dim">
          Last session {status.status.replace("_", " ")} — P&amp;L {money(status.total_pnl)}.
        </div>
      ) : null}

      {!autopilot ? (
        <div className="flex items-center justify-between gap-2 border border-hal-amber/30 bg-hal-amber/[0.06] px-2 py-2 text-[11px] text-hal-amber-bright">
          <span>Scalper needs autopilot ("robo trader") mode.</span>
          <button
            type="button"
            onClick={() => setTradeMode("autopilot")}
            className="shrink-0 border border-hal-amber/50 px-2 py-1 text-[10px] uppercase tracking-[1px] text-hal-amber hover:bg-hal-amber/15"
          >
            Enable
          </button>
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-3">
        <Field label="Capital $">
          <input
            type="number"
            min={0}
            value={capital}
            onChange={(e) => setCapital(e.target.value)}
            className={inputCls}
          />
        </Field>
        <Field label="Profit target $">
          <input
            type="number"
            min={0}
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            className={inputCls}
          />
        </Field>
        <Field label="Loss floor $ (opt)">
          <input
            type="number"
            min={0}
            placeholder="= target"
            value={loss}
            onChange={(e) => setLoss(e.target.value)}
            className={inputCls}
          />
        </Field>
        <Field label="Period">
          <div className="flex border border-hal-red/25">
            {(["day", "week"] as const).map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setPeriod(p)}
                className={cn(
                  "flex-1 px-2 py-1.5 text-[11px] uppercase tracking-[1px]",
                  period === p
                    ? "bg-hal-red/20 text-hal-red-glow"
                    : "text-hal-text-dim hover:text-hal-text",
                )}
              >
                {p}
              </button>
            ))}
          </div>
        </Field>
      </div>

      <button
        type="button"
        disabled={!canStart}
        onClick={onStart}
        className={cn(
          "border px-3 py-2.5 text-[12px] uppercase tracking-[2px] transition-colors",
          canStart
            ? "border-hal-red/60 bg-hal-red/15 text-hal-red-glow hover:bg-hal-red/30"
            : "cursor-not-allowed border-hal-text-dim/20 text-hal-text-dim/50",
        )}
      >
        Arm scalper
      </button>
    </div>
  );
}

const inputCls =
  "w-full border border-hal-red/25 bg-black/40 px-2 py-1.5 text-[13px] text-hal-text outline-none focus:border-hal-red/60 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[9px] uppercase tracking-[2px] text-hal-text-dim">{label}</span>
      {children}
    </label>
  );
}
