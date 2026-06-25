// Tiny drag primitives shared by the terminal's resizable frames — no external
// dependency. DragHandle reports an incremental pixel delta as you drag (x or y)
// using pointer capture, so the same component drives both the column dividers
// (axis="x") and a panel's bottom height handle (axis="y"). clamp keeps the
// resulting size within sane bounds.

import { useRef } from "react";
import { cn } from "@/lib/cn";

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function DragHandle({
  axis,
  onDrag,
  className,
}: {
  axis: "x" | "y";
  /** Incremental movement in px since the last event (right/down positive). */
  onDrag: (delta: number) => void;
  className?: string;
}) {
  const last = useRef(0);

  const onPointerDown = (e: React.PointerEvent) => {
    e.preventDefault();
    last.current = axis === "x" ? e.clientX : e.clientY;
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (e.buttons !== 1) return; // only while the primary button is held
    const cur = axis === "x" ? e.clientX : e.clientY;
    const delta = cur - last.current;
    last.current = cur;
    if (delta) onDrag(delta);
  };

  return (
    <div
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      role="separator"
      aria-orientation={axis === "x" ? "vertical" : "horizontal"}
      className={cn(
        "group/handle shrink-0 touch-none",
        axis === "x" ? "w-1.5 cursor-col-resize self-stretch" : "h-1.5 w-full cursor-row-resize",
        className,
      )}
    >
      {/* A faint rule that brightens to amber on hover so the grab area reads. */}
      <div
        className={cn(
          "bg-term-border transition-colors group-hover/handle:bg-term-amber/60",
          axis === "x" ? "mx-auto h-full w-px" : "my-auto h-px w-full",
        )}
      />
    </div>
  );
}
