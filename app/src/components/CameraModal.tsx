import { useEffect, useRef, useState } from "react";
import { captureFrameFromVideo } from "@/lib/vision";
import { useAttachments } from "@/stores/attachments";

interface CameraModalProps {
  open: boolean;
  onClose: () => void;
  /** Optional callback fired after a successful snap (with the new attachment count). */
  onSnap?: () => void;
}

type Facing = "environment" | "user";

export default function CameraModal({ open, onClose, onSnap }: CameraModalProps) {
  const addImage = useAttachments((s) => s.addImage);
  const flashError = useAttachments((s) => s.flashError);

  const [facing, setFacing] = useState<Facing>("environment");
  const [error, setError] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const stop = () => {
    streamRef.current?.getTracks().forEach((t) => {
      try {
        t.stop();
      } catch {
        /* ignore */
      }
    });
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  };

  // (Re)acquire the stream whenever the modal opens or the facing flips.
  useEffect(() => {
    if (!open) {
      stop();
      return;
    }
    let cancelled = false;
    setError(null);
    (async () => {
      try {
        stop();
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: facing },
          audio: false,
        });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          void videoRef.current.play().catch(() => {});
        }
      } catch (err) {
        setError(`Camera unavailable: ${(err as Error).message}`);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, facing]);

  // Cleanup on unmount.
  useEffect(() => () => stop(), []);

  // ESC closes the modal.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const snap = () => {
    const base64 = captureFrameFromVideo(videoRef.current);
    if (!base64) {
      flashError("Snap failed: empty image");
      return;
    }
    addImage(`camera-${Date.now()}.jpg`, base64);
    onSnap?.();
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[250] flex flex-col items-center justify-center gap-4 bg-black/95 p-5">
      {error ? (
        <div className="border border-hal-amber/60 bg-hal-amber/10 px-4 py-2 font-mono text-[12px] text-hal-amber">
          {error}
        </div>
      ) : (
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="max-h-[70vh] max-w-[92vw] border-2 border-hal-red bg-black shadow-[0_0_40px_rgba(255,30,30,0.4)]"
        />
      )}

      <div className="flex gap-4">
        <button
          type="button"
          onClick={onClose}
          className="border border-hal-red bg-hal-red/[0.08] px-7 py-3 font-display text-[11px] uppercase tracking-[4px] text-hal-red transition-colors hover:bg-hal-red/20 hover:text-white"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={() => setFacing((f) => (f === "environment" ? "user" : "environment"))}
          className="border border-hal-red bg-hal-red/[0.08] px-7 py-3 font-display text-[11px] uppercase tracking-[4px] text-hal-red transition-colors hover:bg-hal-red/20 hover:text-white"
        >
          Flip
        </button>
        <button
          type="button"
          onClick={snap}
          disabled={!!error}
          className="border border-hal-red bg-hal-red/20 px-7 py-3 font-display text-[11px] uppercase tracking-[4px] text-white transition-all hover:bg-hal-red hover:shadow-[0_0_30px_rgba(255,30,30,0.6)] disabled:cursor-not-allowed disabled:opacity-40"
        >
          Snap
        </button>
      </div>
    </div>
  );
}
