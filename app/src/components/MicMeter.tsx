// Real-time mic input visualizer — vertical spectrum bars driven by an
// AnalyserNode on the live MediaStream. Visible only while recording.

import { useEffect, useRef } from "react";
import { useConnection } from "@/stores/connection";

const BAR_COUNT = 48;
const FFT_SIZE = 128; // smallest valid; gives 64 bins, we sample down to BAR_COUNT

export default function MicMeter() {
  const stream = useConnection((s) => s.micStream);
  const recording = useConnection((s) => s.recording);
  const cancelRecording = useConnection((s) => s.cancelRecording);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!stream || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx2d = canvas.getContext("2d");
    if (!ctx2d) return;

    const Ctor =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext })
        .webkitAudioContext;
    const audioCtx = new Ctor();
    const source = audioCtx.createMediaStreamSource(stream);
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = FFT_SIZE;
    analyser.smoothingTimeConstant = 0.7;
    source.connect(analyser);

    const bins = analyser.frequencyBinCount;
    const data = new Uint8Array(bins);
    let raf = 0;
    let cancelled = false;

    // Resize canvas to match display size (handle DPR for crisp bars).
    const dpr = window.devicePixelRatio || 1;
    const cssWidth = canvas.clientWidth;
    const cssHeight = canvas.clientHeight;
    canvas.width = cssWidth * dpr;
    canvas.height = cssHeight * dpr;
    ctx2d.scale(dpr, dpr);

    const draw = () => {
      if (cancelled) return;
      analyser.getByteFrequencyData(data);
      ctx2d.clearRect(0, 0, cssWidth, cssHeight);

      const barGap = 2;
      const totalGap = barGap * (BAR_COUNT - 1);
      const barWidth = (cssWidth - totalGap) / BAR_COUNT;
      // Stretch the lower freqs (where voice lives) by sampling non-linearly.
      const binsPerBar = bins / BAR_COUNT;

      for (let i = 0; i < BAR_COUNT; i++) {
        const startBin = Math.floor(i * binsPerBar);
        const endBin = Math.max(startBin + 1, Math.floor((i + 1) * binsPerBar));
        let max = 0;
        for (let j = startBin; j < endBin && j < bins; j++) {
          if (data[j] > max) max = data[j];
        }
        const v = max / 255;
        const barH = Math.max(1, v * cssHeight);
        const x = i * (barWidth + barGap);
        const y = cssHeight - barH;

        // Gradient: dim red at base → bright red at top.
        const grad = ctx2d.createLinearGradient(0, cssHeight, 0, y);
        grad.addColorStop(0, "rgba(138, 0, 0, 0.7)");
        grad.addColorStop(1, `rgba(255, ${30 + v * 30}, ${30 + v * 30}, ${0.6 + v * 0.4})`);
        ctx2d.fillStyle = grad;
        ctx2d.fillRect(x, y, barWidth, barH);
      }

      raf = requestAnimationFrame(draw);
    };
    draw();

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      try {
        source.disconnect();
      } catch {
        /* ignore */
      }
      audioCtx.close().catch(() => {});
    };
  }, [stream]);

  if (!recording || !stream) return null;

  return (
    <div className="immersive-fade fixed bottom-[240px] left-1/2 z-30 -translate-x-1/2">
      <div className="relative">
        <canvas
          ref={canvasRef}
          className="block h-10 w-[300px] border border-hal-red/40 bg-black/70 shadow-[0_0_18px_rgba(255,30,30,0.35)] backdrop-blur-sm"
        />
        {/* Stop listening: stands the mic down immediately without sending a
            turn. Pinned just right of the graph so it stays clear of the
            centered spectrum. */}
        <button
          type="button"
          onClick={() => cancelRecording()}
          data-tauri-drag-region="false"
          title="Stop listening"
          aria-label="Stop listening"
          className="absolute left-full top-1/2 ml-2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full border border-hal-red/45 bg-hal-red/[0.08] text-hal-text transition-all hover:border-hal-red hover:bg-hal-red/25 hover:text-white hover:shadow-[0_0_14px_rgba(255,30,30,0.45)]"
        >
          <svg
            className="h-[18px] w-[18px]"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <rect x="6" y="6" width="12" height="12" rx="1.5" fill="currentColor" />
          </svg>
        </button>
      </div>
    </div>
  );
}
