import { useConnection } from "@/stores/connection";
import { useImmersive } from "@/stores/immersive";
import { cn } from "@/lib/cn";

/** The HAL eye — a glowing red ring (Jarvis-style) with counter-rotating
 *  arc sweeps, radial tick marks, and a molten core at center. Speed and
 *  intensity react to the body.<mode> class set by the connection store. */
export default function Eye() {
  const startRecording = useConnection((s) => s.startRecording);
  const immersive = useImmersive((s) => s.active);

  return (
    <div
      className={cn(
        "hal-panel relative flex items-center justify-center transition-all duration-500",
        immersive
          ? "fixed bottom-4 right-4 z-[60] h-[150px] w-[150px] drop-shadow-[0_0_18px_rgba(255,30,30,0.45)] hover:scale-105"
          : "h-[480px] w-[480px]",
      )}
    >
      <button
        type="button"
        onClick={() => startRecording()}
        aria-label="Activate HAL"
        className={cn(
          "hal-eye relative cursor-pointer rounded-full",
          immersive ? "h-[120px] w-[120px]" : "h-80 w-80",
        )}
      >
        {/* Soft outer glow halo */}
        <span className="hal-ring-glow pointer-events-none absolute left-1/2 top-1/2 h-[90%] w-[90%] -translate-x-1/2 -translate-y-1/2 rounded-full" />
        {/* Radial tick marks just outside the ring */}
        <span className="hal-ticks pointer-events-none absolute left-1/2 top-1/2 h-[104%] w-[104%] -translate-x-1/2 -translate-y-1/2 rounded-full" />
        {/* Counter-rotating arc sweeps */}
        <span className="hal-arc-outer pointer-events-none absolute left-1/2 top-1/2 h-full w-full -translate-x-1/2 -translate-y-1/2 rounded-full" />
        <span className="hal-arc-inner pointer-events-none absolute left-1/2 top-1/2 h-[74%] w-[74%] -translate-x-1/2 -translate-y-1/2 rounded-full" />
        {/* Bright main ring */}
        <span className="hal-ring pointer-events-none absolute left-1/2 top-1/2 h-[90%] w-[90%] -translate-x-1/2 -translate-y-1/2 rounded-full" />
        {/* Dark center socket with molten core */}
        <span className="hal-core-disc pointer-events-none absolute left-1/2 top-1/2 flex h-[64%] w-[64%] -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full">
          <span className="hal-core pointer-events-none h-[18%] w-[18%] rounded-full" />
        </span>
      </button>
    </div>
  );
}
