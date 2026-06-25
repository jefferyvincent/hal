// Shared building blocks for the terminal tabs: a titled panel frame and a set
// of compact number formatters. Centralised so every tab reads identically
// (DRY) and the amber/black skin stays consistent.

import { useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { DragHandle, clamp } from "@/components/terminal/resize";

export function Panel({
  title,
  right,
  className,
  bodyClassName,
  children,
  resizable = false,
  defaultHeight = 280,
  minHeight = 140,
}: {
  title: string;
  right?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
  /** When set, the panel gets a drag handle along its bottom edge so the user
   *  can pull it taller (its body scrolls). Height is local to the panel. */
  resizable?: boolean;
  defaultHeight?: number;
  minHeight?: number;
}) {
  const [height, setHeight] = useState(defaultHeight);
  return (
    <section
      className={cn(
        "flex min-h-0 flex-col border border-term-border bg-term-panel",
        className,
      )}
      style={resizable ? { height } : undefined}
    >
      <header className="flex items-center justify-between border-b border-term-border bg-term-panel-2 px-2.5 py-1.5">
        <span className="text-[10px] font-bold uppercase tracking-[3px] text-term-amber">
          {title}
        </span>
        {right ? <div className="flex items-center gap-2">{right}</div> : null}
      </header>
      <div className={cn("min-h-0 flex-1 overflow-auto", bodyClassName)}>{children}</div>
      {resizable ? (
        <DragHandle
          axis="y"
          onDrag={(dy) => setHeight((h) => clamp(h + dy, minHeight, 2000))}
          className="border-t border-term-border"
        />
      ) : null}
    </section>
  );
}

// A label/value cell used across the KPI strips and summary grids.
export function Stat({
  label,
  value,
  color,
  sub,
}: {
  label: string;
  value: ReactNode;
  color?: string;
  sub?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-0.5 border border-term-border bg-term-panel px-2.5 py-2">
      <span className="text-[9px] uppercase tracking-[2px] text-term-text-dim">{label}</span>
      <span className="text-[15px] font-bold leading-none" style={color ? { color } : undefined}>
        {value}
      </span>
      {sub ? <span className="text-[9px] text-term-text-dim">{sub}</span> : null}
    </div>
  );
}

export function Empty({ text }: { text: string }) {
  return (
    <div className="flex h-full items-center justify-center p-4 text-center text-[10px] uppercase tracking-[2px] text-term-muted">
      {text}
    </div>
  );
}

export const POS = "#2ecc71";
export const NEG = "#ff453a";
export const AMBER = "#ffb000";

export function money(n: number | null | undefined, max = 0): string {
  if (n == null) return "—";
  return n.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: max,
  });
}

export function pct(frac: number | null | undefined, digits = 2): string {
  if (frac == null) return "—";
  const p = frac * 100;
  return `${p >= 0 ? "+" : ""}${p.toFixed(digits)}%`;
}

// Compact magnitude (1.2T / 340.5B / 12.3M) for market cap, revenue, FCF.
export function compact(n: number | null | undefined): string {
  if (n == null) return "—";
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(2)}K`;
  return `${sign}$${abs.toFixed(0)}`;
}

export function num(n: number | null | undefined, digits = 2): string {
  return typeof n === "number" ? n.toFixed(digits) : "—";
}
