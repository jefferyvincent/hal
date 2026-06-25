// A radial "coverage network" for the Equity tab — the company at the hub with a
// spoke out to every broker firm that publishes a rating on it (the real
// brokerNames list from Nasdaq's analyst endpoint). It mirrors the relationship
// graph in FinceptTerminal's Equity Research screen, but driven by data HAL
// actually has rather than a stubbed supply chain. Pure SVG, no deps.

import { useMemo } from "react";

const AMBER = "#ffb000";
const AMBER_DIM = "#a6730a";
const TEXT_DIM = "#8a8470";

// Trim Nasdaq's all-caps, abbreviated firm names to something that fits a label.
function shorten(name: string): string {
  const s = name.replace(/\s+/g, " ").trim();
  return s.length > 14 ? `${s.slice(0, 13)}…` : s;
}

export default function CoverageGraph({
  symbol,
  brokers,
  rating,
  count,
}: {
  symbol: string;
  brokers: string[];
  rating: string | null;
  count: number | null;
}) {
  // Lay the firms evenly around a circle. viewBox is a 200×200 square; the hub
  // sits at the centre and spokes reach toward the edge. Memoised so the layout
  // is stable across re-renders.
  const nodes = useMemo(() => {
    const cx = 100;
    const cy = 100;
    const r = 78;
    const n = brokers.length;
    if (n === 0) return [];
    return brokers.map((name, i) => {
      // Start at the top (-90°) and go clockwise.
      const angle = (i / n) * 2 * Math.PI - Math.PI / 2;
      const x = cx + r * Math.cos(angle);
      const y = cy + r * Math.sin(angle);
      // Anchor labels so they read outward from the hub.
      const anchor: "start" | "middle" | "end" =
        Math.abs(Math.cos(angle)) < 0.3 ? "middle" : x < cx ? "end" : "start";
      const lx = cx + (r + 4) * Math.cos(angle);
      const ly = cy + (r + 4) * Math.sin(angle);
      return { name, x, y, lx, ly, anchor };
    });
  }, [brokers]);

  if (brokers.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-center text-[10px] uppercase tracking-[2px] text-term-muted">
        No analyst coverage
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <svg viewBox="0 0 200 200" className="min-h-0 w-full flex-1" preserveAspectRatio="xMidYMid meet">
        {/* Spokes */}
        {nodes.map((node) => (
          <line
            key={`l-${node.name}`}
            x1={100}
            y1={100}
            x2={node.x}
            y2={node.y}
            stroke={AMBER_DIM}
            strokeWidth={0.4}
            strokeOpacity={0.5}
          />
        ))}
        {/* Firm nodes + labels */}
        {nodes.map((node) => (
          <g key={`n-${node.name}`}>
            <circle cx={node.x} cy={node.y} r={1.6} fill={AMBER} />
            <text
              x={node.lx}
              y={node.ly}
              fill={TEXT_DIM}
              fontSize={3.4}
              textAnchor={node.anchor}
              dominantBaseline="middle"
              className="font-mono"
            >
              {shorten(node.name)}
            </text>
          </g>
        ))}
        {/* Hub */}
        <circle cx={100} cy={100} r={11} fill="#0a0b0d" stroke={AMBER} strokeWidth={0.8} />
        <text x={100} y={100} fill={AMBER} fontSize={5} textAnchor="middle" dominantBaseline="middle" className="font-mono font-bold">
          {symbol}
        </text>
      </svg>
      <div className="flex items-center justify-between border-t border-term-border px-2 py-1 text-[9px] uppercase tracking-[1px] text-term-text-dim">
        <span>
          {count ?? brokers.length} firms
        </span>
        {rating ? <span className="font-bold text-term-amber">{rating}</span> : null}
      </div>
    </div>
  );
}
