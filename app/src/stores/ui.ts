import { create } from "zustand";

interface UiState {
  conversationsOpen: boolean;
  telemetryHidden: boolean;
  positionSizingOpen: boolean;
  positionsOpen: boolean;
  mcpOpen: boolean;
  subscriptionsOpen: boolean;
  scalperOpen: boolean;
  cognitionOpen: boolean;
  dashboardOpen: boolean;
  terminalOpen: boolean;
  chatOpen: boolean;
  fullscreenChat: boolean;
  toggleConversations: () => void;
  setTelemetryHidden: (hidden: boolean) => void;
  togglePositionSizing: () => void;
  togglePositions: () => void;
  toggleMcp: () => void;
  toggleSubscriptions: () => void;
  toggleScalper: () => void;
  toggleCognition: () => void;
  setCognitionOpen: (open: boolean) => void;
  toggleDashboard: () => void;
  setDashboardOpen: (open: boolean) => void;
  toggleTerminal: () => void;
  setTerminalOpen: (open: boolean) => void;
  toggleChatOpen: () => void;
  setChatOpen: (open: boolean) => void;
  toggleFullscreenChat: () => void;
}

export const useUi = create<UiState>((set) => ({
  conversationsOpen: false,
  telemetryHidden: true,
  positionSizingOpen: false,
  positionsOpen: false,
  mcpOpen: false,
  subscriptionsOpen: false,
  scalperOpen: false,
  cognitionOpen: false,
  dashboardOpen: false,
  terminalOpen: false,
  // Chat is hidden by default so the eye sits alone, uncluttered. The
  // Chat button in Controls toggles it on; closing also drops fullscreen.
  chatOpen: false,
  fullscreenChat: false,

  toggleConversations: () =>
    set((s) => ({ conversationsOpen: !s.conversationsOpen })),

  setTelemetryHidden: (hidden) => set({ telemetryHidden: hidden }),

  togglePositionSizing: () =>
    set((s) => ({ positionSizingOpen: !s.positionSizingOpen })),

  togglePositions: () => set((s) => ({ positionsOpen: !s.positionsOpen })),

  toggleMcp: () => set((s) => ({ mcpOpen: !s.mcpOpen })),

  toggleSubscriptions: () =>
    set((s) => ({ subscriptionsOpen: !s.subscriptionsOpen })),

  toggleScalper: () => set((s) => ({ scalperOpen: !s.scalperOpen })),

  toggleCognition: () => set((s) => ({ cognitionOpen: !s.cognitionOpen })),

  setCognitionOpen: (open) => set({ cognitionOpen: open }),

  toggleDashboard: () => set((s) => ({ dashboardOpen: !s.dashboardOpen })),

  setDashboardOpen: (open) => set({ dashboardOpen: open }),

  toggleTerminal: () => set((s) => ({ terminalOpen: !s.terminalOpen })),

  setTerminalOpen: (open) => set({ terminalOpen: open }),

  toggleChatOpen: () =>
    set((s) => {
      const next = !s.chatOpen;
      if (!next) {
        document.body.classList.remove("fullscreen-chat");
        return { chatOpen: false, fullscreenChat: false };
      }
      return { chatOpen: true };
    }),

  setChatOpen: (open) =>
    set((s) => {
      if (s.chatOpen === open) return s;
      if (!open) {
        document.body.classList.remove("fullscreen-chat");
        return { chatOpen: false, fullscreenChat: false };
      }
      return { chatOpen: true };
    }),

  toggleFullscreenChat: () =>
    set((s) => {
      const next = !s.fullscreenChat;
      document.body.classList.toggle("fullscreen-chat", next);
      return { fullscreenChat: next };
    }),
}));
