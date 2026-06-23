// Voice-activity detector: end-of-utterance trigger for hands-free mode.
// Ported from the legacy implementation. We watch RMS energy on the mic
// stream and call `onEndOfSpeech()` once we've had enough silence after
// a confirmed speech burst.

export interface VadOptions {
  /** Threshold for "speech detected" (linear RMS, 0..1). */
  rmsThreshold?: number;
  /** Milliseconds of trailing silence required to call EOS. */
  silenceMs?: number;
  /** Fired once, the first time a speech burst is confirmed. Lets callers
   *  cancel a "patience" timeout once the user has actually started talking. */
  onSpeechStart?: () => void;
  /** AudioContext to attach to (we'll reuse one if you pass it). */
  ctx?: AudioContext;
}

export class Vad {
  private ctx: AudioContext;
  private analyser: AnalyserNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private rafId: number | null = null;
  private threshold: number;
  private silenceMs: number;
  private onEnd: () => void;
  private onSpeechStart: (() => void) | null;
  private hadSpeech = false;
  private silenceStart: number | null = null;

  constructor(onEndOfSpeech: () => void, opts: VadOptions = {}) {
    this.onEnd = onEndOfSpeech;
    this.onSpeechStart = opts.onSpeechStart ?? null;
    this.threshold = opts.rmsThreshold ?? 0.018;
    this.silenceMs = opts.silenceMs ?? 1200;
    this.ctx =
      opts.ctx ??
      new (window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext })
          .webkitAudioContext)();
  }

  start(stream: MediaStream) {
    this.stop();
    this.source = this.ctx.createMediaStreamSource(stream);
    this.analyser = this.ctx.createAnalyser();
    this.analyser.fftSize = 1024;
    this.source.connect(this.analyser);
    const buf = new Float32Array(this.analyser.fftSize);
    this.hadSpeech = false;
    this.silenceStart = null;

    const tick = () => {
      if (!this.analyser) return;
      this.analyser.getFloatTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
      const rms = Math.sqrt(sum / buf.length);
      const now = performance.now();
      if (rms > this.threshold) {
        if (!this.hadSpeech) this.onSpeechStart?.();
        this.hadSpeech = true;
        this.silenceStart = null;
      } else if (this.hadSpeech) {
        if (this.silenceStart === null) this.silenceStart = now;
        else if (now - this.silenceStart > this.silenceMs) {
          this.onEnd();
          this.stop();
          return;
        }
      }
      this.rafId = requestAnimationFrame(tick);
    };
    this.rafId = requestAnimationFrame(tick);
  }

  stop() {
    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
    try {
      this.source?.disconnect();
    } catch {
      /* ignore */
    }
    this.source = null;
    this.analyser = null;
  }
}
