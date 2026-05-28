import type { ReactNode } from "react";
import { useConnection } from "@/stores/connection";
import { useImmersive } from "@/stores/immersive";
import { useUi } from "@/stores/ui";
import { cn } from "@/lib/cn";

function AuxBtn({
  onClick,
  active,
  title,
  children,
}: {
  onClick: () => void;
  active?: boolean;
  title: string;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className={cn(
        "flex h-12 w-12 items-center justify-center rounded-full border border-hal-red/35 bg-hal-red/[0.06] text-hal-text transition-all",
        "hover:border-hal-red hover:bg-hal-red/25 hover:text-white hover:shadow-[0_0_18px_rgba(255,30,30,0.5)]",
        active && "border-hal-red bg-hal-red/30 text-white shadow-[0_0_18px_rgba(255,30,30,0.5)]",
      )}
    >
      {children}
    </button>
  );
}

const ICON = "h-5 w-5";

export default function Controls() {
  const mode = useConnection((s) => s.mode);
  const recording = useConnection((s) => s.recording);
  const startRecording = useConnection((s) => s.startRecording);
  const stopRecording = useConnection((s) => s.stopRecording);
  const abort = useConnection((s) => s.abort);
  const wipe = useConnection((s) => s.wipe);
  const fastMode = useConnection((s) => s.fastMode);
  const toggleFastMode = useConnection((s) => s.toggleFastMode);

  const chatOpen = useUi((s) => s.chatOpen);
  const toggleChat = useUi((s) => s.toggleChatOpen);
  const fullscreenChat = useUi((s) => s.fullscreenChat);
  const toggleFullscreen = useUi((s) => s.toggleFullscreenChat);

  const immersiveActive = useImmersive((s) => s.active);
  const enterImmersive = useImmersive((s) => s.enter);
  const exitImmersive = useImmersive((s) => s.exit);

  const onMicClick = () => {
    if (recording) stopRecording();
    else void startRecording();
  };

  return (
    <div className="immersive-fade fixed bottom-[150px] left-1/2 z-20 flex -translate-x-1/2 items-center gap-4">
      {/* Left cluster: wipe, stop, fast/smart */}
      <AuxBtn onClick={() => void wipe()} title="Wipe memory">
        <svg
          className={ICON}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="3 6 5 6 21 6" />
          <path d="M19 6l-1.5 14a2 2 0 0 1-2 1.8H8.5a2 2 0 0 1-2-1.8L5 6" />
          <path d="M10 11v6" />
          <path d="M14 11v6" />
        </svg>
      </AuxBtn>

      <AuxBtn onClick={() => void abort()} title="Stop HAL">
        <svg className={ICON} viewBox="0 0 24 24" fill="currentColor">
          <rect x="6" y="6" width="12" height="12" rx="1" />
        </svg>
      </AuxBtn>

      <button
        type="button"
        onClick={toggleFastMode}
        title={
          fastMode
            ? "Currently FAST model — click to switch to SMART"
            : "Currently SMART model — click to switch to FAST"
        }
        className={cn(
          "relative flex h-12 w-12 items-center justify-center rounded-full border transition-all",
          fastMode
            ? "border-hal-amber bg-hal-amber/20 text-hal-amber-bright shadow-[0_0_18px_rgba(255,179,0,0.55)] hover:bg-hal-amber/30"
            : "border-hal-red/35 bg-hal-red/[0.06] text-hal-text hover:border-hal-red hover:bg-hal-red/25 hover:text-white",
        )}
      >
        <svg
          className={ICON}
          viewBox="0 0 24 24"
          fill={fastMode ? "currentColor" : "none"}
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
        </svg>
        <span
          className={cn(
            "pointer-events-none absolute -bottom-3.5 text-[8px] font-bold tracking-[2px]",
            fastMode ? "text-hal-amber-bright" : "text-hal-text-dim",
          )}
        >
          {fastMode ? "FAST" : "SMART"}
        </span>
      </button>

      {/* Center: microphone (primary action). Quiet when idle, lights up
          dramatically when actually recording. */}
      <button
        type="button"
        title={recording ? "Stop listening" : "Talk to HAL"}
        onClick={onMicClick}
        className={cn(
          "flex h-20 w-20 items-center justify-center rounded-full border transition-all",
          recording || mode === "listening"
            ? "animate-pulse border-2 border-hal-red bg-hal-red/40 text-white shadow-[0_0_40px_rgba(255,30,30,0.7)]"
            : "border-hal-red/35 bg-hal-red/[0.06] text-hal-text hover:border-hal-red hover:bg-hal-red/25 hover:text-white hover:shadow-[0_0_30px_rgba(255,30,30,0.45)]",
        )}
      >
        <svg
          className="h-8 w-8"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <rect x="9" y="3" width="6" height="12" rx="3" />
          <path d="M5 11a7 7 0 0 0 14 0" />
          <line x1="12" y1="18" x2="12" y2="22" />
          <line x1="8" y1="22" x2="16" y2="22" />
        </svg>
      </button>

      {/* Right cluster: chat, [fullscreen — only when chat is on], immersive */}
      <AuxBtn
        onClick={toggleChat}
        active={chatOpen}
        title={chatOpen ? "Hide chat transcript" : "Show chat transcript"}
      >
        <svg
          className={ICON}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      </AuxBtn>

      {chatOpen ? (
        <AuxBtn
          onClick={toggleFullscreen}
          active={fullscreenChat}
          title={fullscreenChat ? "Exit fullscreen chat" : "Fullscreen chat"}
        >
          <svg
            className={ICON}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="15 3 21 3 21 9" />
            <polyline points="9 21 3 21 3 15" />
            <line x1="21" y1="3" x2="14" y2="10" />
            <line x1="3" y1="21" x2="10" y2="14" />
          </svg>
        </AuxBtn>
      ) : null}

      <AuxBtn
        onClick={() => (immersiveActive ? exitImmersive() : void enterImmersive())}
        active={immersiveActive}
        title="Immersive mode (see what HAL sees)"
      >
        <svg
          className={ICON}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="3" />
          <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
        </svg>
      </AuxBtn>

    </div>
  );
}
