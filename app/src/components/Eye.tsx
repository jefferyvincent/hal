import { useConnection } from "@/stores/connection";
import { useImmersive } from "@/stores/immersive";
import { cn } from "@/lib/cn";

/** The HAL 9000 eye — digital-signal styling with sweeping scanline +
 *  dot-matrix noise pattern over the red iris core. */
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
      {/* Decorative pin dots on the hex plate */}
      <span className="pointer-events-none absolute left-1/2 top-[30px] h-2 w-2 -translate-x-1/2 rounded-full bg-[radial-gradient(circle,#2a2a2f_30%,#050507_80%)]" />
      <span className="pointer-events-none absolute bottom-[30px] left-1/2 h-2 w-2 -translate-x-1/2 rounded-full bg-[radial-gradient(circle,#2a2a2f_30%,#050507_80%)]" />

      <button
        type="button"
        onClick={() => startRecording()}
        aria-label="Activate HAL"
        className={cn(
          "hal-eye relative cursor-pointer overflow-hidden rounded-full",
          immersive ? "h-[120px] w-[120px]" : "h-80 w-80",
        )}
      >
        <span
          className={cn(
            "hal-eye-iris pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full",
            immersive ? "h-[60px] w-[60px]" : "h-[160px] w-[160px]",
          )}
        />
        <span
          className={cn(
            "hal-eye-pupil pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full",
            immersive ? "h-3 w-3" : "h-[22px] w-[22px]",
          )}
        />
        <span className="hal-eye-specular pointer-events-none absolute left-[28%] top-[22%] h-[30px] w-[60px] rounded-full" />

        {/* Dot-matrix noise pattern over the whole eye */}
        <span className="hal-eye-noise pointer-events-none absolute inset-0" />

        {/* Horizontal scanline sweeping top-to-bottom */}
        <span className="hal-eye-scanline pointer-events-none absolute left-[-5%] top-0 h-[3px] w-[110%]" />
      </button>
    </div>
  );
}
