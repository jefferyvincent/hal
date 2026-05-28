// Custom min / max / close buttons for the frameless Tauri window.
// Browser dev mode (npm run dev) renders nothing — there's no window to control.

import { useEffect, useState } from "react";

const ICON = "h-2.5 w-2.5";

export default function WindowControls() {
  const [isTauri, setIsTauri] = useState(false);

  // Detect Tauri at mount time. Same heuristic the WS uses.
  useEffect(() => {
    const onTauri =
      window.location.hostname === "tauri.localhost" ||
      typeof (window as unknown as { __TAURI_INTERNALS__?: unknown })
        .__TAURI_INTERNALS__ !== "undefined";
    setIsTauri(onTauri);
  }, []);

  if (!isTauri) return null;

  const call = async (
    method: "minimize" | "toggleMaximize" | "close",
  ): Promise<void> => {
    try {
      const mod = await import("@tauri-apps/api/window");
      const w = mod.getCurrentWindow();
      if (method === "minimize") await w.minimize();
      else if (method === "toggleMaximize") await w.toggleMaximize();
      else await w.close();
    } catch (err) {
      console.warn("WindowControls:", err);
    }
  };

  return (
    <div
      className="fixed right-0 top-0 z-[110] flex"
      data-tauri-drag-region="false"
    >
      <button
        type="button"
        onClick={() => void call("minimize")}
        title="Minimize"
        aria-label="Minimize"
        className="flex h-7 w-11 items-center justify-center text-hal-text-dim transition-colors hover:bg-hal-red/20 hover:text-white"
      >
        <svg className={ICON} viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.2">
          <line x1="1" y1="5" x2="9" y2="5" />
        </svg>
      </button>

      <button
        type="button"
        onClick={() => void call("toggleMaximize")}
        title="Maximize / Restore"
        aria-label="Maximize"
        className="flex h-7 w-11 items-center justify-center text-hal-text-dim transition-colors hover:bg-hal-red/20 hover:text-white"
      >
        <svg className={ICON} viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.2">
          <rect x="1" y="1" width="8" height="8" />
        </svg>
      </button>

      <button
        type="button"
        onClick={() => void call("close")}
        title="Close"
        aria-label="Close"
        className="flex h-7 w-11 items-center justify-center text-hal-text-dim transition-colors hover:bg-hal-red hover:text-white"
      >
        <svg className={ICON} viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.2">
          <line x1="1" y1="1" x2="9" y2="9" />
          <line x1="9" y1="1" x2="1" y2="9" />
        </svg>
      </button>
    </div>
  );
}
