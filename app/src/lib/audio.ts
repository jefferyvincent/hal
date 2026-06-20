// Streamed audio playback queue. Mirrors the legacy implementation: each
// incoming binary chunk is a self-contained WAV that we decode and schedule
// to play back-to-back with no gap.

export class AudioPlayer {
  private ctx: AudioContext | null = null;
  // Master gain all chunks route through, so mute can silence output without
  // disturbing the decode/schedule timeline (drain still fires, mode machine
  // keeps working — HAL "speaks" silently).
  private gain: GainNode | null = null;
  private muted = false;
  private nextChunkStart = 0;
  private isPlaying = false;
  private idleTimer: number | null = null;
  private onDrainCb: (() => void) | null = null;
  // Serializes decode+schedule so chunks are placed on the timeline in arrival
  // order. decodeAudioData is async, so without this, chunks that arrive in a
  // burst decode concurrently and race on nextChunkStart — scheduling
  // overlapping sources, which sounds like stuttering/garbled speech.
  private chain: Promise<void> = Promise.resolve();
  // Bumped on flush(). Chunks captured before a flush are dropped even if their
  // async decode was already in flight — otherwise stale audio from an
  // interrupted turn schedules onto the new context and plays over the top
  // (overlap = stuttering / sped-up garble).
  private epoch = 0;

  /** Lazily build / resume the AudioContext (browser autoplay rules). */
  async ensureContext(): Promise<AudioContext> {
    if (!this.ctx) {
      const Ctor =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.ctx = new Ctor();
    }
    if (!this.gain) {
      this.gain = this.ctx.createGain();
      this.gain.gain.value = this.muted ? 0 : 1;
      this.gain.connect(this.ctx.destination);
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

  /** Silence/unsilence output. Keeps decoding & scheduling so the mode machine
   *  (which keys off `playing`) is unaffected — only the audible output changes. */
  setMuted(muted: boolean): void {
    this.muted = muted;
    if (this.gain) this.gain.gain.value = muted ? 0 : 1;
  }

  get isMuted(): boolean {
    return this.muted;
  }

  /** Fire when the last queued chunk has finished playing. */
  onDrain(cb: () => void) {
    this.onDrainCb = cb;
  }

  /** Enqueue a single WAV blob for gap-free playback. Calls are serialized so
   *  chunks land on the timeline in arrival order regardless of decode timing. */
  queue(buffer: ArrayBuffer): Promise<void> {
    const epoch = this.epoch;
    this.chain = this.chain
      .then(() => this._decodeAndSchedule(buffer, epoch))
      .catch((err) => console.warn("AudioPlayer: chunk failed", err));
    return this.chain;
  }

  private async _decodeAndSchedule(buffer: ArrayBuffer, epoch: number): Promise<void> {
    if (epoch !== this.epoch) return; // flushed after this chunk was queued
    const ctx = await this.ensureContext();
    let audioBuffer: AudioBuffer;
    try {
      audioBuffer = await ctx.decodeAudioData(buffer.slice(0));
    } catch (err) {
      console.warn("AudioPlayer: skip chunk", err);
      return;
    }
    if (epoch !== this.epoch) return; // flushed while decoding — drop it
    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(this.gain ?? ctx.destination);
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
    this.epoch += 1;  // invalidate any in-flight chunks queued before this flush
    this.chain = Promise.resolve();  // drop any pending decode/schedule work
    // Best-effort: closing & rebuilding the context kills any in-flight
    // sources. Cheaper than tracking each source manually.
    if (this.ctx) {
      this.ctx.close().catch(() => {});
      this.ctx = null;
      this.gain = null;  // rebuilt on next ensureContext, mute state preserved
    }
  }

  get playing(): boolean {
    return this.isPlaying;
  }
}
