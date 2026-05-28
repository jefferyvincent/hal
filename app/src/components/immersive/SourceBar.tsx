import { useImmersive } from "@/stores/immersive";
import type { ImmersiveSource } from "@/types";
import { cn } from "@/lib/cn";

const SOURCES: { id: Exclude<ImmersiveSource, "off">; label: string }[] = [
  { id: "camera", label: "Camera" },
  { id: "screen", label: "Screen" },
  { id: "map", label: "Map" },
  { id: "video", label: "Video" },
];

export default function SourceBar() {
  const active = useImmersive((s) => s.active);
  const source = useImmersive((s) => s.source);
  const setSource = useImmersive((s) => s.setSource);
  const exit = useImmersive((s) => s.exit);

  if (!active) return null;

  return (
    <div className="fixed left-1/2 top-3.5 z-[65] flex -translate-x-1/2 gap-1.5 border border-hal-red/35 bg-[rgba(8,8,11,0.6)] p-1.5 opacity-30 backdrop-blur-md transition-opacity duration-500 hover:opacity-100 hover:duration-200">
      {SOURCES.map((s) => (
        <button
          key={s.id}
          type="button"
          onClick={() => {
            if (s.id === "video") {
              const url = window.prompt("Video URL (mp4 / webm)?", "");
              if (!url) return;
              void setSource("video", { url });
              return;
            }
            void setSource(s.id);
          }}
          className={cn(
            "border border-hal-red/30 bg-hal-red/[0.06] px-2.5 py-1.5 font-display text-[9px] uppercase tracking-[2px] text-hal-text transition-all",
            "hover:bg-hal-red/20 hover:text-white",
            source === s.id &&
              "border-hal-red bg-hal-red/30 text-white shadow-[0_0_12px_rgba(255,30,30,0.4)]",
          )}
        >
          {s.label}
        </button>
      ))}
      <button
        type="button"
        onClick={exit}
        className="border border-hal-amber/50 bg-hal-red/[0.06] px-2.5 py-1.5 font-display text-[9px] uppercase tracking-[2px] text-hal-amber hover:bg-hal-amber/20 hover:text-white"
      >
        Exit
      </button>
    </div>
  );
}
