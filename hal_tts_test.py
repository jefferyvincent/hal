import wave
from piper import PiperVoice
from hal.brainstem.config import PIPER_VOICE_PATH

v = PiperVoice.load(PIPER_VOICE_PATH, use_cuda=False)
chunks = list(v.synthesize("Hello Tyler, this is HAL speaking. Can you hear me?"))
first = chunks[0]
pcm = b"".join(c.audio_int16_bytes for c in chunks)
out = "/media/tylerchianelli/HAL/repos/hal/hal_tts_test.wav"
with wave.open(out, "wb") as wf:
    wf.setnchannels(first.sample_channels)
    wf.setsampwidth(first.sample_width)
    wf.setframerate(first.sample_rate)
    wf.writeframes(pcm)
print(f"channels={first.sample_channels} width={first.sample_width} "
      f"rate={first.sample_rate} pcm_bytes={len(pcm)}")
print(f"wrote {out}")
