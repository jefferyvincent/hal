// The terminal's command line — a Bloomberg-style "type a command, hit GO" bar.
// A bare ticker focuses the terminal on that symbol (and loads its research);
// short verbs (CHART / DD / BACKTEST / SCREEN / NEWS) translate to the prompts
// HAL already understands and route to the right tab; anything else is sent to
// HAL verbatim as a question. Up/Down walks the command history.

import { useRef, useState } from "react";
import { useConnection } from "@/stores/connection";
import { useTerminal, type TerminalTab } from "@/stores/terminal";

const TICKER_RE = /^[A-Z]{1,5}$/;

const TAB_WORDS: Record<string, TerminalTab> = {
  OVERVIEW: "overview", OVW: "overview", F1: "overview",
  PORTFOLIO: "portfolio", PORT: "portfolio", POS: "portfolio", F2: "portfolio",
  NEWS: "news", N: "news", F3: "news",
  EQUITY: "equity", EQ: "equity", DES: "equity", F4: "equity",
  NODES: "nodes", NODE: "nodes", F5: "nodes",
};

export default function CommandLine() {
  const [text, setText] = useState("");
  const [hist, setHist] = useState<string[]>([]);
  const [histIdx, setHistIdx] = useState<number | null>(null);
  const [hint, setHint] = useState<string>("");
  const inputRef = useRef<HTMLInputElement>(null);

  const sendText = useConnection((s) => s.sendText);
  const loadEquity = useConnection((s) => s.loadEquity);
  const setSymbol = useTerminal((s) => s.setSymbol);
  const setTab = useTerminal((s) => s.setTab);
  const symbol = useTerminal((s) => s.symbol);

  const flash = (msg: string) => {
    setHint(msg);
    window.setTimeout(() => setHint(""), 2500);
  };

  const run = (raw: string) => {
    const t = raw.trim();
    if (!t) return;
    setHist((h) => [t, ...h].slice(0, 50));
    setHistIdx(null);

    const parts = t.split(/\s+/);
    const head = parts[0].toUpperCase();
    const rest = parts.slice(1);
    const sym = (rest[0]?.toUpperCase() || symbol).replace(/[^A-Z.]/g, "");

    // Tab navigation words.
    if (TAB_WORDS[head] && rest.length === 0) {
      setTab(TAB_WORDS[head]);
      return;
    }

    // Verbs → existing HAL prompts.
    if (head === "CHART" || head === "C") {
      const tf = rest[1] || "5m";
      setSymbol(sym);
      setTab("overview");
      void sendText(`show me a ${tf} chart of ${sym}`);
      flash(`Charting ${sym} ${tf}`);
      return;
    }
    if (head === "DD" || head === "COMMITTEE" || head === "CMTE") {
      setSymbol(sym);
      setTab("overview");
      void sendText(`deep dive on ${sym}`);
      flash(`Convening committee on ${sym}`);
      return;
    }
    if (head === "BACKTEST" || head === "BT") {
      setSymbol(sym);
      setTab("overview");
      void sendText(`backtest ${sym}`);
      flash(`Backtesting ${sym}`);
      return;
    }
    if (head === "OPTIMIZE" || head === "OPT") {
      setSymbol(sym);
      setTab("overview");
      void sendText(`optimize ${sym}`);
      flash(`Optimizing ${sym}`);
      return;
    }
    if (head === "SCREEN" || head === "OPTS") {
      setSymbol(sym);
      void sendText(`screen options for ${sym}`);
      flash(`Screening options on ${sym}`);
      return;
    }
    if (head === "NEWS" && rest.length) {
      setTab("news");
      void sendText(`watch news for ${sym}`);
      flash(`Watching news for ${sym}`);
      return;
    }
    if (head === "EQ" || head === "DES" || head === "FA") {
      setSymbol(sym);
      loadEquity(sym);
      setTab("equity");
      flash(`Research ${sym}`);
      return;
    }

    // Bare ticker → focus terminal on it + load research.
    if (parts.length === 1 && TICKER_RE.test(head)) {
      setSymbol(head);
      loadEquity(head);
      setTab("equity");
      flash(`${head} loaded`);
      return;
    }

    // Anything else: ask HAL directly.
    void sendText(t);
    flash("Sent to HAL");
  };

  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      run(text);
      setText("");
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (hist.length === 0) return;
      const next = histIdx === null ? 0 : Math.min(histIdx + 1, hist.length - 1);
      setHistIdx(next);
      setText(hist[next]);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (histIdx === null) return;
      const next = histIdx - 1;
      if (next < 0) {
        setHistIdx(null);
        setText("");
      } else {
        setHistIdx(next);
        setText(hist[next]);
      }
    }
  };

  return (
    <div className="flex items-center gap-2 border-t border-term-border bg-term-panel-2 px-3 py-1.5">
      <span className="text-[11px] font-bold tracking-[2px] text-term-amber">{symbol}</span>
      <span className="text-term-muted">›</span>
      <input
        ref={inputRef}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKey}
        spellCheck={false}
        autoComplete="off"
        placeholder="ticker, or CHART / DD / BACKTEST / SCREEN / NEWS / EQ … or ask HAL anything"
        className="flex-1 bg-transparent text-[12px] text-term-text placeholder:text-term-muted/70 outline-none"
      />
      {hint ? <span className="text-[10px] uppercase tracking-[1px] text-term-cyan">{hint}</span> : null}
      <button
        type="button"
        onClick={() => {
          run(text);
          setText("");
        }}
        className="border border-term-amber bg-term-amber/15 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-[2px] text-term-amber hover:bg-term-amber/30"
      >
        GO
      </button>
    </div>
  );
}
