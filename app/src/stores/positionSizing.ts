// Broker selection: the one position-related setting still kept in the UI.
// Account total comes from Alpaca and risk policy from the vault trading rules
// (both read server-side), so neither is duplicated here. Persisted to
// localStorage so the chosen broker survives restarts.

import { create } from "zustand";

const STORAGE_KEY = "hal.positionSizing";

/** Brokers HAL knows. Alpaca is the integrated execution broker (HAL places
 *  orders directly); the rest are instruction-only (HAL tailors order steps). */
export const BROKERS = ["Alpaca", "Webull", "Robinhood", "Schwab", "Fidelity", "IBKR", "Tastytrade", "E*TRADE"] as const;
export type Broker = (typeof BROKERS)[number];

export interface PositionSizingState {
  /** Broker HAL tailors order instructions to. */
  broker: Broker;
  setBroker: (v: Broker) => void;
}

interface Persisted {
  broker: Broker;
}

const DEFAULTS: Persisted = {
  broker: "Alpaca",
};

function load(): Persisted {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    const parsed = JSON.parse(raw) as Partial<Persisted>;
    return {
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

  setBroker(v) {
    set({ broker: v });
    save({ broker: get().broker });
  },
}));
