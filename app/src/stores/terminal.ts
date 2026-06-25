// Terminal-mode UI state: which function-key tab is showing and the symbol the
// terminal is focused on. Kept separate from useUi (overlay open/close) and
// useConnection (server data) so the terminal's own view state doesn't churn
// either of those stores. The command line and the tab strip both write here;
// the panels read from it.

import { create } from "zustand";

export type TerminalTab =
  | "overview"
  | "portfolio"
  | "news"
  | "equity"
  | "nodes";

export const TERMINAL_TABS: { id: TerminalTab; key: string; label: string }[] = [
  { id: "overview", key: "F1", label: "OVERVIEW" },
  { id: "portfolio", key: "F2", label: "PORTFOLIO" },
  { id: "news", key: "F3", label: "NEWS" },
  { id: "equity", key: "F4", label: "EQUITY" },
  { id: "nodes", key: "F5", label: "NODES" },
];

interface TerminalState {
  tab: TerminalTab;
  /** The instrument the terminal is centred on. Drives the Equity tab fetch and
   *  the command line's default subject. */
  symbol: string;
  setTab: (tab: TerminalTab) => void;
  setSymbol: (symbol: string) => void;
}

export const useTerminal = create<TerminalState>((set) => ({
  tab: "overview",
  symbol: "SPY",
  setTab: (tab) => set({ tab }),
  setSymbol: (symbol) => set({ symbol: symbol.toUpperCase().trim() || "SPY" }),
}));
