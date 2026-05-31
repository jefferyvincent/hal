import { create } from "zustand";

interface UiState {
  conversationsOpen: boolean;
  telemetryHidden: boolean;
  positionSizingOpen: boolean;
  chatOpen: boolean;
  fullscreenChat: boolean;
  toggleConversations: () => void;
  setTelemetryHidden: (hidden: boolean) => void;
  togglePositionSizing: () => void;
  toggleChatOpen: () => void;
  setChatOpen: (open: boolean) => void;
  toggleFullscreenChat: () => void;
}

export const useUi = create<UiState>((set) => ({
  conversationsOpen: false,
  telemetryHidden: true,
  positionSizingOpen: false,
  // Chat is hidden by default so the eye sits alone, uncluttered. The
  // Chat button in Controls toggles it on; closing also drops fullscreen.
  chatOpen: false,
  fullscreenChat: false,

  toggleConversations: () =>
    set((s) => ({ conversationsOpen: !s.conversationsOpen })),

  setTelemetryHidden: (hidden) => set({ telemetryHidden: hidden }),

  togglePositionSizing: () =>
    set((s) => ({ positionSizingOpen: !s.positionSizingOpen })),

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
