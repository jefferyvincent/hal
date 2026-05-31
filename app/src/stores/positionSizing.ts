// Position-sizing settings: account size and the risk parameters HAL uses
// to size an options trade. Persisted to localStorage so the account size
// and the user's risk preferences survive restarts.

import { create } from "zustand";

const STORAGE_KEY = "hal.positionSizing";

/** Brokers HAL knows how to give order-entry instructions for. */
export const BROKERS = ["Webull", "Robinhood", "Schwab", "Fidelity", "IBKR", "Tastytrade", "E*TRADE"] as const;
export type Broker = (typeof BROKERS)[number];

export interface PositionSizingState {
  /** Total account size in dollars. */
  accountSize: number;
  /** Max fraction of the account to risk on a single trade, as a percent. */
  maxRiskPct: number;
  /** Stop-loss as a percent of the premium paid. */
  stopLossPct: number;
  /** Broker HAL tailors order instructions to. */
  broker: Broker;
  setAccountSize: (v: number) => void;
  setMaxRiskPct: (v: number) => void;
  setStopLossPct: (v: number) => void;
  setBroker: (v: Broker) => void;
}

interface Persisted {
  accountSize: number;
  maxRiskPct: number;
  stopLossPct: number;
  broker: Broker;
}

const DEFAULTS: Persisted = {
  accountSize: 0,
  maxRiskPct: 5,
  stopLossPct: 20,
  broker: "Webull",
};

function load(): Persisted {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    const parsed = JSON.parse(raw) as Partial<Persisted>;
    return {
      accountSize: Number.isFinite(parsed.accountSize) ? (parsed.accountSize as number) : DEFAULTS.accountSize,
      maxRiskPct: Number.isFinite(parsed.maxRiskPct) ? (parsed.maxRiskPct as number) : DEFAULTS.maxRiskPct,
      stopLossPct: Number.isFinite(parsed.stopLossPct) ? (parsed.stopLossPct as number) : DEFAULTS.stopLossPct,
      broker: BROKERS.includes(parsed.broker as Broker) ? (parsed.broker as Broker) : DEFAULTS.broker,
    };
  } catch {
    return DEFAULTS;
  }
}

function save(s: Persisted): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch {
    /* ignore quota / unavailable storage */
  }
}

export const usePositionSizing = create<PositionSizingState>((set, get) => ({
  ...load(),

  setAccountSize(v) {
    const accountSize = Math.max(0, v || 0);
    set({ accountSize });
    save({ ...persistable(get()), accountSize });
  },

  setMaxRiskPct(v) {
    const maxRiskPct = Math.min(100, Math.max(0, v || 0));
    set({ maxRiskPct });
    save({ ...persistable(get()), maxRiskPct });
  },

  setStopLossPct(v) {
    const stopLossPct = Math.min(100, Math.max(0, v || 0));
    set({ stopLossPct });
    save({ ...persistable(get()), stopLossPct });
  },

  setBroker(v) {
    set({ broker: v });
    save({ ...persistable(get()), broker: v });
  },
}));

function persistable(s: PositionSizingState): Persisted {
  return {
    accountSize: s.accountSize,
    maxRiskPct: s.maxRiskPct,
    stopLossPct: s.stopLossPct,
    broker: s.broker,
  };
}

/** Pure sizing math, exported so it can be unit-tested independently.
 *  Qty = floor( (account × maxRisk%) / (price × 100 × stopLoss%) ). */
export function sizePosition(
  accountSize: number,
  maxRiskPct: number,
  stopLossPct: number,
  price: number,
): { riskBudget: number; costPerContract: number; riskPerContract: number; qty: number; totalCost: number; totalRisk: number } {
  const riskBudget = accountSize * (maxRiskPct / 100);
  const costPerContract = price * 100;
  const riskPerContract = costPerContract * (stopLossPct / 100);
  const qty = riskPerContract > 0 ? Math.floor(riskBudget / riskPerContract) : 0;
  return {
    riskBudget,
    costPerContract,
    riskPerContract,
    qty,
    totalCost: qty * costPerContract,
    totalRisk: qty * riskPerContract,
  };
}
