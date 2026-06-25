// F5 NODES — a visual workflow editor (FinceptTerminal's node-editor idea, in
// HAL's idiom). Each node is one of HAL's existing capabilities; you wire a
// Symbol node into action nodes and hit RUN, which dispatches the matching
// commands HAL already understands (it answers in the chat / drives the other
// tabs). Deliberately dependency-free: nodes are absolutely-positioned divs,
// edges are SVG beziers, drag is pointer events — no graph library.
//
// This is the interactive build/execute surface; persistence is localStorage so
// a workflow survives a reload. Execution is intentionally simple (resolve each
// action node's symbol from an upstream Symbol node, fire its HAL command in
// order) rather than a full dataflow engine.

import { useCallback, useEffect, useRef, useState } from "react";
import { useConnection } from "@/stores/connection";
import { useTerminal } from "@/stores/terminal";
import { cn } from "@/lib/cn";

type NodeKind = "symbol" | "chart" | "committee" | "backtest" | "screen" | "watch";

interface GraphNode {
  id: string;
  kind: NodeKind;
  x: number;
  y: number;
  value: string; // symbol for "symbol" node; timeframe/side for others
  status?: "idle" | "running" | "done";
}

interface Edge {
  from: string; // node id (output)
  to: string; // node id (input)
}

const NODE_W = 168;
const NODE_H = 66;

const NODE_META: Record<NodeKind, { label: string; color: string; hasInput: boolean; prompt?: (sym: string, v: string) => string }> = {
  symbol: { label: "SYMBOL", color: "#ffb000", hasInput: false },
  chart: { label: "CHART", color: "#3fb6e0", hasInput: true, prompt: (s, v) => `show me a ${v || "5m"} chart of ${s}` },
  committee: { label: "COMMITTEE", color: "#2ecc71", hasInput: true, prompt: (s) => `deep dive on ${s}` },
  backtest: { label: "BACKTEST", color: "#ffd166", hasInput: true, prompt: (s) => `backtest ${s}` },
  screen: { label: "SCREEN OPTIONS", color: "#c792ea", hasInput: true, prompt: (s, v) => `screen ${v || "call"} options for ${s}` },
  watch: { label: "WATCH NEWS", color: "#ff8c42", hasInput: true, prompt: (s) => `watch news for ${s}` },
};

const PALETTE: NodeKind[] = ["symbol", "chart", "committee", "backtest", "screen", "watch"];
const STORE_KEY = "hal.terminal.nodegraph";

let _seq = 0;
function uid(): string {
  _seq += 1;
  return `n${Date.now().toString(36)}${_seq}`;
}

function load(): { nodes: GraphNode[]; edges: Edge[] } | null {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    return raw ? (JSON.parse(raw) as { nodes: GraphNode[]; edges: Edge[] }) : null;
  } catch {
    return null;
  }
}

export default function NodesTab() {
  const sendText = useConnection((s) => s.sendText);
  const termSymbol = useTerminal((s) => s.symbol);

  const initial = load();
  const [nodes, setNodes] = useState<GraphNode[]>(
    initial?.nodes ?? [
      { id: "seed-sym", kind: "symbol", x: 60, y: 80, value: termSymbol },
      { id: "seed-chart", kind: "chart", x: 320, y: 60, value: "5m" },
      { id: "seed-comm", kind: "committee", x: 320, y: 170, value: "" },
    ],
  );
  const [edges, setEdges] = useState<Edge[]>(
    initial?.edges ?? [
      { from: "seed-sym", to: "seed-chart" },
      { from: "seed-sym", to: "seed-comm" },
    ],
  );
  // Pending connection: the output node the user clicked first.
  const [linkFrom, setLinkFrom] = useState<string | null>(null);
  const canvasRef = useRef<HTMLDivElement>(null);

  // Persist on change.
  useEffect(() => {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify({ nodes, edges }));
    } catch {
      /* ignore */
    }
  }, [nodes, edges]);

  const addNode = (kind: NodeKind) => {
    setNodes((ns) => [
      ...ns,
      { id: uid(), kind, x: 60 + Math.random() * 80, y: 60 + ns.length * 12, value: kind === "symbol" ? termSymbol : kind === "chart" ? "5m" : kind === "screen" ? "call" : "" },
    ]);
  };

  const removeNode = (id: string) => {
    setNodes((ns) => ns.filter((n) => n.id !== id));
    setEdges((es) => es.filter((e) => e.from !== id && e.to !== id));
  };

  // Drag a node by its header.
  const dragState = useRef<{ id: string; dx: number; dy: number } | null>(null);
  const onHeaderDown = (e: React.PointerEvent, n: GraphNode) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    dragState.current = { id: n.id, dx: e.clientX - rect.left - n.x, dy: e.clientY - rect.top - n.y };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  };
  const onPointerMove = (e: React.PointerEvent) => {
    const ds = dragState.current;
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!ds || !rect) return;
    const x = Math.max(0, e.clientX - rect.left - ds.dx);
    const y = Math.max(0, e.clientY - rect.top - ds.dy);
    setNodes((ns) => ns.map((n) => (n.id === ds.id ? { ...n, x, y } : n)));
  };
  const onPointerUp = () => {
    dragState.current = null;
  };

  // Port click → start/finish a connection.
  const onOutputClick = (id: string) => setLinkFrom(id);
  const onInputClick = (id: string) => {
    if (linkFrom && linkFrom !== id) {
      setEdges((es) => {
        if (es.some((e) => e.from === linkFrom && e.to === id)) return es;
        return [...es, { from: linkFrom, to: id }];
      });
    }
    setLinkFrom(null);
  };

  const symbolFor = useCallback(
    (nodeId: string): string => {
      const up = edges.find((e) => e.to === nodeId);
      if (up) {
        const src = nodes.find((n) => n.id === up.from && n.kind === "symbol");
        if (src && src.value) return src.value.toUpperCase();
      }
      return termSymbol;
    },
    [edges, nodes, termSymbol],
  );

  // Run: fire each action node's HAL command in sequence, small gap between so
  // the server isn't slammed and the chat reads in order.
  const [running, setRunning] = useState(false);
  const run = async () => {
    if (running) return;
    setRunning(true);
    const actions = nodes.filter((n) => n.kind !== "symbol");
    for (const n of actions) {
      const meta = NODE_META[n.kind];
      if (!meta.prompt) continue;
      const sym = symbolFor(n.id);
      setNodes((ns) => ns.map((x) => (x.id === n.id ? { ...x, status: "running" } : x)));
      try {
        await sendText(meta.prompt(sym, n.value));
      } catch {
        /* ignore individual failures */
      }
      setNodes((ns) => ns.map((x) => (x.id === n.id ? { ...x, status: "done" } : x)));
      await new Promise((r) => setTimeout(r, 600));
    }
    setRunning(false);
  };

  return (
    <div className="flex h-full flex-col">
      {/* Toolbar */}
      <div className="flex items-center gap-2 border-b border-term-border bg-term-panel-2 px-2 py-1.5">
        <span className="mr-1 text-[9px] uppercase tracking-[2px] text-term-text-dim">Add:</span>
        {PALETTE.map((k) => (
          <button
            key={k}
            type="button"
            onClick={() => addNode(k)}
            className="border border-term-border px-2 py-0.5 text-[9px] uppercase tracking-[1px] text-term-text-dim hover:border-term-amber hover:text-term-amber"
          >
            + {NODE_META[k].label}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          {linkFrom ? (
            <span className="text-[9px] uppercase tracking-[1px] text-term-cyan">
              click an input port… <button type="button" onClick={() => setLinkFrom(null)} className="text-term-text-dim hover:text-term-red">cancel</button>
            </span>
          ) : null}
          <button
            type="button"
            onClick={run}
            disabled={running}
            className={cn(
              "border px-3 py-0.5 text-[10px] font-bold uppercase tracking-[2px]",
              running
                ? "border-term-amber-dim text-term-amber-dim"
                : "border-term-amber bg-term-amber/15 text-term-amber hover:bg-term-amber/30",
            )}
          >
            {running ? "Running…" : "▶ Run"}
          </button>
        </div>
      </div>

      {/* Canvas */}
      <div
        ref={canvasRef}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        className="relative min-h-0 flex-1 overflow-auto bg-term-bg"
        style={{ backgroundImage: "radial-gradient(rgba(255,176,0,0.07) 1px, transparent 1px)", backgroundSize: "22px 22px" }}
      >
        {/* Edges */}
        <svg className="pointer-events-none absolute inset-0 h-full w-full" style={{ minHeight: "100%" }}>
          {edges.map((e, i) => {
            const a = nodes.find((n) => n.id === e.from);
            const b = nodes.find((n) => n.id === e.to);
            if (!a || !b) return null;
            const x1 = a.x + NODE_W;
            const y1 = a.y + NODE_H / 2;
            const x2 = b.x;
            const y2 = b.y + NODE_H / 2;
            const mx = (x1 + x2) / 2;
            return (
              <path
                key={i}
                d={`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`}
                fill="none"
                stroke="rgba(255,176,0,0.5)"
                strokeWidth={1.5}
              />
            );
          })}
        </svg>

        {/* Nodes */}
        {nodes.map((n) => {
          const meta = NODE_META[n.kind];
          return (
            <div
              key={n.id}
              className="absolute select-none border bg-term-panel shadow-[0_0_12px_rgba(0,0,0,0.6)]"
              style={{ left: n.x, top: n.y, width: NODE_W, borderColor: meta.color }}
            >
              <div
                onPointerDown={(e) => onHeaderDown(e, n)}
                className="flex cursor-grab items-center justify-between px-2 py-1"
                style={{ background: `${meta.color}22` }}
              >
                <span className="text-[9px] font-bold uppercase tracking-[1px]" style={{ color: meta.color }}>
                  {meta.label}
                </span>
                <span className="flex items-center gap-1.5">
                  {n.status === "running" ? <span className="text-[8px] text-term-amber">●</span> : null}
                  {n.status === "done" ? <span className="text-[8px] text-term-green">✓</span> : null}
                  <button
                    type="button"
                    onClick={() => removeNode(n.id)}
                    className="text-[10px] text-term-muted hover:text-term-red"
                  >
                    ✕
                  </button>
                </span>
              </div>

              <div className="px-2 py-1.5">
                {n.kind === "symbol" ? (
                  <input
                    value={n.value}
                    onChange={(e) =>
                      setNodes((ns) => ns.map((x) => (x.id === n.id ? { ...x, value: e.target.value.toUpperCase() } : x)))
                    }
                    className="w-full border border-term-border bg-term-bg px-1.5 py-1 text-center text-[13px] font-bold tracking-[2px] text-term-amber outline-none"
                  />
                ) : n.kind === "chart" ? (
                  <select
                    value={n.value}
                    onChange={(e) => setNodes((ns) => ns.map((x) => (x.id === n.id ? { ...x, value: e.target.value } : x)))}
                    className="w-full border border-term-border bg-term-bg px-1 py-1 text-[11px] text-term-text outline-none"
                  >
                    {["5m", "15m", "1h", "1d", "1w"].map((tf) => (
                      <option key={tf} value={tf}>{tf}</option>
                    ))}
                  </select>
                ) : n.kind === "screen" ? (
                  <select
                    value={n.value}
                    onChange={(e) => setNodes((ns) => ns.map((x) => (x.id === n.id ? { ...x, value: e.target.value } : x)))}
                    className="w-full border border-term-border bg-term-bg px-1 py-1 text-[11px] text-term-text outline-none"
                  >
                    <option value="call">calls</option>
                    <option value="put">puts</option>
                  </select>
                ) : (
                  <div className="py-1 text-center text-[9px] uppercase tracking-[1px] text-term-text-dim">
                    {symbolFor(n.id)}
                  </div>
                )}
              </div>

              {/* Ports */}
              {meta.hasInput ? (
                <button
                  type="button"
                  title="input"
                  onClick={() => onInputClick(n.id)}
                  className="absolute -left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 rounded-full border-2 border-term-cyan bg-term-bg hover:bg-term-cyan"
                />
              ) : null}
              <button
                type="button"
                title="output — click then click a target input"
                onClick={() => onOutputClick(n.id)}
                className={cn(
                  "absolute -right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 rounded-full border-2 bg-term-bg",
                  linkFrom === n.id ? "border-term-amber bg-term-amber" : "border-term-amber hover:bg-term-amber",
                )}
              />
            </div>
          );
        })}

        {nodes.length === 0 ? (
          <div className="flex h-full items-center justify-center text-[10px] uppercase tracking-[2px] text-term-muted">
            Add nodes from the toolbar, wire a Symbol into actions, then Run.
          </div>
        ) : null}
      </div>

      <div className="border-t border-term-border bg-term-panel-2 px-3 py-1 text-[8px] uppercase tracking-[2px] text-term-muted">
        Drag headers to move · click output ● then an input ○ to connect · Run fires each action through HAL
      </div>
    </div>
  );
}
