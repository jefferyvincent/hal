// Streamed audio playback queue. Mirrors the legacy implementation: each
// incoming binary chunk is a self-contained WAV that we decode and schedule
// to play back-to-back with no gap.

export class AudioPlayer {
  private ctx: AudioContext | null = null;
  private nextChunkStart = 0;
  private isPlaying = false;
  private idleTimer: number | null = null;
  private onDrainCb: (() => void) | null = null;

  /** Lazily build / resume the AudioContext (browser autoplay rules). */
  async ensureContext(): Promise<AudioContext> {
    if (!this.ctx) {
      const Ctor =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.ctx = new Ctor();
    }
    if (this.ctx.state === "suspended") {
      try {
        await this.ctx.resume();
      } catch {
        /* swallow — playback simply won't start */
      }
    }
    return this.ctx;
  }

  /** Fire when the last queued chunk has finished playing. */
  onDrain(cb: () => void) {
    this.onDrainCb = cb;
  }

  /** Enqueue a single WAV blob for gap-free playback. */
  async queue(buffer: ArrayBuffer): Promise<void> {
    const ctx = await this.ensureContext();
    let audioBuffer: AudioBuffer;
    try {
      audioBuffer = await ctx.decodeAudioData(buffer.slice(0));
    } catch (err) {
      console.warn("AudioPlayer: skip chunk", err);
      return;
    }
    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(ctx.destination);
    const now = ctx.currentTime;
    const startAt = this.isPlaying ? this.nextChunkStart : now + 0.06;
    source.start(startAt);
    this.nextChunkStart = startAt + audioBuffer.duration;
    this.isPlaying = true;

    if (this.idleTimer !== null) {
      clearTimeout(this.idleTimer);
      this.idleTimer = null;
    }
    const msUntilEnd = Math.max(
      0,
      (this.nextChunkStart - ctx.currentTime) * 1000 + 80,
    );
    this.idleTimer = window.setTimeout(() => {
      this.isPlaying = false;
      this.onDrainCb?.();
    }, msUntilEnd);
  }

  /** Stop everything immediately, drop queued chunks. */
  flush(): void {
    if (this.idleTimer !== null) {
      clearTimeout(this.idleTimer);
      this.idleTimer = null;
    }
    this.nextChunkStart = 0;
    this.isPlaying = false;
    // Best-effort: closing & rebuilding the context kills any in-flight
    // sources. Cheaper than tracking each source manually.
    if (this.ctx) {
      this.ctx.close().catch(() => {});
      this.ctx = null;
    }
  }

  get playing(): boolean {
    return this.isPlaying;
  }
}
