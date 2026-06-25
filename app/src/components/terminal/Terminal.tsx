// The Terminal overlay — a FinceptTerminal/Bloomberg-style workspace that opens
// over the rest of HAL (voice/eye keep running underneath; Esc or the header
// closes it). A function-key tab strip up top, the active panel in the middle,
// and a command line at the bottom. It's a useUi overlay like Dashboard, in the
// amber/black `term-*` skin rather than HAL's red/amber chrome.

import { useEffect } from "react";
import { useUi } from "@/stores/ui";
import { useConnection } from "@/stores/connection";
import { useTerminal, TERMINAL_TABS, type TerminalTab } from "@/stores/terminal";
import { isMarketOpen } from "@/lib/marketSession";
import { cn } from "@/lib/cn";
import CommandLine from "@/components/terminal/CommandLine";
import OverviewTab from "@/components/terminal/tabs/OverviewTab";
import PortfolioTab from "@/components/terminal/tabs/PortfolioTab";
import NewsTab from "@/components/terminal/tabs/NewsTab";
import EquityTab from "@/components/terminal/tabs/EquityTab";
import NodesTab from "@/components/terminal/tabs/NodesTab";

const FKEY_TO_TAB: Record<string, TerminalTab> = {
  F1: "overview",
  F2: "portfolio",
  F3: "news",
  F4: "equity",
  F5: "nodes",
};

function Clock() {
  // Lightweight wall clock in ET-ish local time; purely cosmetic chrome.
  const now = new Date();
  return (
    <span className="tabular-nums text-term-text-dim">
      {now.toLocaleTimeString(undefined, { hour12: false })}
    </span>
  );
}

export default function Terminal() {
  const open = useUi((s) => s.terminalOpen);
  const close = useUi((s) => s.setTerminalOpen);
  const mode = useConnection((s) => s.mode);
  const brokerPaper = useConnection((s) => s.brokerPaper);
  const brokerReady = useConnection((s) => s.brokerReady);
  const tab = useTerminal((s) => s.tab);
  const setTab = useTerminal((s) => s.setTab);
  const symbol = useTerminal((s) => s.symbol);

  // F1–F5 switch tabs; Esc closes. Ignore F-keys while typing so they don't
  // hijack the command line (they don't produce text, but be explicit).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        close(false);
        return;
      }
      const t = FKEY_TO_TAB[e.key];
      if (t) {
        e.preventDefault();
        setTab(t);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, close, setTab]);

  if (!open) return null;

  return (
    <div className="terminal fixed inset-0 z-40 flex flex-col bg-term-bg font-mono text-term-text">
      {/* Title bar */}
      <header className="flex items-center justify-between border-b border-term-border bg-term-panel px-3 py-1.5">
        <div className="flex items-baseline gap-3">
          <span className="text-[12px] font-bold uppercase tracking-[5px] text-term-amber">HAL · Terminal</span>
          <span className="text-[9px] uppercase tracking-[2px] text-term-muted">{symbol}</span>
        </div>
        <div className="flex items-center gap-4 text-[9px] uppercase tracking-[2px]">
          <span
            className={cn(
              "border px-1.5 py-0.5",
              isMarketOpen() ? "border-term-green/50 text-term-green" : "border-term-muted text-term-muted",
            )}
          >
            {isMarketOpen() ? "MKT OPEN" : "MKT CLOSED"}
          </span>
          <span className="border border-term-border px-1.5 py-0.5 text-term-text-dim">
            {brokerReady ? (brokerPaper ? "PAPER" : "LIVE") : "NO BROKER"}
          </span>
          <span className="text-term-text-dim">HAL · {mode.toUpperCase()}</span>
          <Clock />
          <button
            type="button"
            onClick={() => close(false)}
            className="text-term-text-dim hover:text-term-amber"
            title="Close terminal (Esc)"
          >
            ✕
          </button>
        </div>
      </header>

      {/* Function-key tab strip */}
      <nav className="flex items-stretch border-b border-term-border bg-term-panel">
        {TERMINAL_TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={cn(
              "flex items-center gap-1.5 border-r border-term-border px-3.5 py-1.5 text-[10px] uppercase tracking-[2px] transition-colors",
              tab === t.id
                ? "bg-term-amber/15 text-term-amber"
                : "text-term-text-dim hover:bg-term-panel-2 hover:text-term-text",
            )}
          >
            <span className="text-term-muted">{t.key}</span>
            <span className="font-bold">{t.label}</span>
          </button>
        ))}
      </nav>

      {/* Active panel */}
      <main className="relative min-h-0 flex-1 overflow-hidden">
        {tab === "overview" && <OverviewTab />}
        {tab === "portfolio" && <PortfolioTab />}
        {tab === "news" && <NewsTab />}
        {tab === "equity" && <EquityTab />}
        {tab === "nodes" && <NodesTab />}
      </main>

      <CommandLine />
    </div>
  );
}
