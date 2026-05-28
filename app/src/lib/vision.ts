// Camera + screen + frame capture helpers.

export function pickSupportedMimeType(): string {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4;codecs=mp4a.40.2",
    "audio/mp4",
    "audio/aac",
    "",
  ];
  for (const c of candidates) {
    if (c === "" || MediaRecorder.isTypeSupported?.(c)) return c;
  }
  return "";
}

/** Encode a single frame from a <video> element as base64 JPEG.
 *  Returns null if the element has no video data yet or if the canvas was
 *  tainted by a cross-origin source. */
export function captureFrameFromVideo(videoEl: HTMLVideoElement | null): string | null {
  if (!videoEl || !videoEl.videoWidth) return null;
  const maxDim = 1280;
  const scale = Math.min(
    1,
    maxDim / Math.max(videoEl.videoWidth, videoEl.videoHeight),
  );
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(videoEl.videoWidth * scale);
  canvas.height = Math.round(videoEl.videoHeight * scale);
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);
  let dataUrl: string;
  try {
    dataUrl = canvas.toDataURL("image/jpeg", 0.85);
  } catch (err) {
    console.warn("captureFrameFromVideo: tainted canvas", err);
    return null;
  }
  return (dataUrl.split(",")[1] || "").trim();
}

export async function openRearCamera(): Promise<MediaStream> {
  return navigator.mediaDevices.getUserMedia({
    video: { facingMode: "environment", width: { ideal: 1280 } },
    audio: false,
  });
}

export async function openScreenShare(): Promise<MediaStream> {
  if (!navigator.mediaDevices.getDisplayMedia) {
    throw new Error("Screen capture not supported in this environment");
  }
  return navigator.mediaDevices.getDisplayMedia({
    video: { frameRate: { ideal: 15 } },
    audio: false,
  });
}
