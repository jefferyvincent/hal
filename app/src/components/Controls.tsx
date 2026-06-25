import { useState, type ReactNode } from "react";
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

// Chevron handle that flanks the mic. Collapsed it points outward ("open me");
// expanded it rotates 180° to point inward ("close me"). Both sides drive the
// same toggle so the cluster reads as "< 0 >" when tucked away.
function ChevronToggle({
  side,
  expanded,
  onClick,
}: {
  side: "left" | "right";
  expanded: boolean;
  onClick: () => void;
}) {
  // Left handle defaults to pointing left; right handle to pointing right.
  // Expanding flips each so the pair points back toward the mic.
  const points = side === "left" ? "15 18 9 12 15 6" : "9 18 15 12 9 6";
  return (
    <button
      type="button"
      onClick={onClick}
      title={expanded ? "Collapse controls" : "Show controls"}
      aria-expanded={expanded}
      className={cn(
        "flex h-9 w-7 items-center justify-center rounded-full text-hal-red/70 transition-all",
        "hover:text-hal-red-glow hover:drop-shadow-[0_0_8px_rgba(255,30,30,0.6)]",
      )}
    >
      <svg
        className={cn("h-4 w-4 transition-transform duration-500", expanded && "rotate-180")}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <polyline points={points} />
      </svg>
    </button>
  );
}

export default function Controls() {
  const mode = useConnection((s) => s.mode);
  const recording = useConnection((s) => s.recording);
  const startRecording = useConnection((s) => s.startRecording);
  const stopRecording = useConnection((s) => s.stopRecording);
  const abort = useConnection((s) => s.abort);
  const wipe = useConnection((s) => s.wipe);
  const newConversation = useConnection((s) => s.newConversation);
  const fastMode = useConnection((s) => s.fastMode);
  const toggleFastMode = useConnection((s) => s.toggleFastMode);

  // Controls rest in the compact "<0>" state — just the mic flanked by two
  // chevrons. Tapping either chevron fans the aux clusters out left and right
  // while the mic stays anchored dead-center.
  const [expanded, setExpanded] = useState(false);
  const toggle = () => setExpanded((v) => !v);

  const chatOpen = useUi((s) => s.chatOpen);
  const toggleChat = useUi((s) => s.toggleChatOpen);
  const terminalOpen = useUi((s) => s.terminalOpen);
  const toggleTerminal = useUi((s) => s.toggleTerminal);
  const fullscreenChat = useUi((s) => s.fullscreenChat);
  const toggleFullscreen = useUi((s) => s.toggleFullscreenChat);

  const immersiveActive = useImmersive((s) => s.active);
  const enterImmersive = useImmersive((s) => s.enter);
  const exitImmersive = useImmersive((s) => s.exit);

  // Push-to-talk: press and hold to talk, release to send. Pointer events
  // cover mouse, touch, and pen. We start on press (push-to-talk mode = no
  // silence auto-cutoff) and stop on release/leave.
  const onMicDown = () => {
    if (!recording) void startRecording(true);
  };
  const onMicUp = () => {
    if (recording) stopRecording();
  };

  return (
    <div className="immersive-fade fixed bottom-[190px] left-1/2 z-20 -translate-x-1/2">
      <div className="relative flex items-center justify-center gap-4">
      {/* Left cluster: new conversation, wipe, stop, fast/smart. Absolutely
          anchored to the left of the chevron so the mic never shifts; fans out
          on expand and tucks back behind the mic on collapse. */}
      <div
        className={cn(
          "absolute right-full top-1/2 flex -translate-y-1/2 items-center gap-4 pr-4 transition-all duration-500 ease-out",
          expanded
            ? "translate-x-0 opacity-100"
            : "pointer-events-none translate-x-10 opacity-0",
        )}
      >
      <AuxBtn onClick={() => void newConversation()} title="New conversation">
        <svg
          className={ICON}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
          <line x1="12" y1="8" x2="12" y2="14" />
          <line x1="9" y1="11" x2="15" y2="11" />
        </svg>
      </AuxBtn>

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

      </div>

      {/* Left chevron handle — the "<" of "<0>". */}
      <ChevronToggle side="left" expanded={expanded} onClick={toggle} />

      {/* Center: microphone (primary action) — the "0", always centered and
          never moved by the reveal animation. Quiet when idle, lights up
          dramatically when actually recording. */}
      <button
        type="button"
        title={recording ? "Release to send" : "Hold to talk"}
        onPointerDown={onMicDown}
        onPointerUp={onMicUp}
        onPointerLeave={() => { if (recording) onMicUp(); }}
        onContextMenu={(e) => e.preventDefault()}
        className={cn(
          "touch-none select-none flex h-20 w-20 items-center justify-center rounded-full border transition-all",
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

      {/* Right chevron handle — the ">" of "<0>". */}
      <ChevronToggle side="right" expanded={expanded} onClick={toggle} />

      {/* Right cluster: chat, [fullscreen — only when chat is on], immersive.
          Absolutely anchored to the right of the chevron; mirrors the left. */}
      <div
        className={cn(
          "absolute left-full top-1/2 flex -translate-y-1/2 items-center gap-4 pl-4 transition-all duration-500 ease-out",
          expanded
            ? "translate-x-0 opacity-100"
            : "pointer-events-none -translate-x-10 opacity-0",
        )}
      >
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
        onClick={toggleTerminal}
        active={terminalOpen}
        title="Terminal (Bloomberg-style market workspace)"
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
          <rect x="2" y="3" width="20" height="18" rx="2" />
          <polyline points="6 9 9 12 6 15" />
          <line x1="12" y1="15" x2="17" y2="15" />
        </svg>
      </AuxBtn>

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

      </div>
    </div>
  );
}
