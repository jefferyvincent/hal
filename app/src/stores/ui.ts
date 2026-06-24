import { create } from "zustand";

interface UiState {
  conversationsOpen: boolean;
  telemetryHidden: boolean;
  positionSizingOpen: boolean;
  positionsOpen: boolean;
  mcpOpen: boolean;
  subscriptionsOpen: boolean;
  cognitionOpen: boolean;
  dashboardOpen: boolean;
  chatOpen: boolean;
  fullscreenChat: boolean;
  toggleConversations: () => void;
  setTelemetryHidden: (hidden: boolean) => void;
  togglePositionSizing: () => void;
  togglePositions: () => void;
  toggleMcp: () => void;
  toggleSubscriptions: () => void;
  toggleCognition: () => void;
  setCognitionOpen: (open: boolean) => void;
  toggleDashboard: () => void;
  setDashboardOpen: (open: boolean) => void;
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
  cognitionOpen: false,
  dashboardOpen: false,
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

  toggleCognition: () => set((s) => ({ cognitionOpen: !s.cognitionOpen })),

  setCognitionOpen: (open) => set({ cognitionOpen: open }),

  toggleDashboard: () => set((s) => ({ dashboardOpen: !s.dashboardOpen })),

  setDashboardOpen: (open) => set({ dashboardOpen: open }),

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
