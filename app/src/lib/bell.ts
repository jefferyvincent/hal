// NYSE-style session bell, synthesized with the Web Audio API (the app ships no
// audio asset for it). Rung when the regular session flips open or closed — see
// App.tsx. "open" rings a brighter, higher peal; "close" a lower, shorter one.

type Bell = "open" | "close";

// Inharmonic partial ratios that read as a struck metal bell rather than a pure
// tone. Roughly those of an idealized bell's hum/prime/tierce/quint modes.
const PARTIALS = [1, 2.76, 5.4, 8.93];
const RING_GAP = 0.26; // seconds between successive rings of the peal

export function playMarketBell(kind: Bell): void {
  const Ctor =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext: typeof AudioContext })
      .webkitAudioContext;
  if (!Ctor) return;

  const ctx = new Ctor();
  // Autoplay rules can leave a fresh context suspended until a user gesture;
  // resume() is harmless when it's already running.
  void ctx.resume?.();

  const fundamental = kind === "open" ? 660 : 440;
  const rings = kind === "open" ? 3 : 2;

  for (let r = 0; r < rings; r++) {
    const t0 = ctx.currentTime + r * RING_GAP;
    PARTIALS.forEach((ratio, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = fundamental * ratio;
      // Upper partials are quieter and die faster — that decay spread is what
      // makes the strike sound metallic instead of like a chord.
      const peak = 0.5 / (i + 1);
      const decay = 1.6 / (i + 1);
      // exponentialRamp can't target 0, so floor at a near-silent value.
      gain.gain.setValueAtTime(0.0001, t0);
      gain.gain.exponentialRampToValueAtTime(peak, t0 + 0.005);
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + decay);
      osc.connect(gain).connect(ctx.destination);
      osc.start(t0);
      osc.stop(t0 + decay + 0.05);
    });
  }

  // Free the context once the whole peal has rung out.
  const total = rings * RING_GAP + 2;
  window.setTimeout(() => void ctx.close?.(), total * 1000);
}
