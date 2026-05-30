import { useEffect, useMemo, useRef } from "react";
import { useImmersive } from "@/stores/immersive";
import { captureFrameFromVideo } from "@/lib/vision";
import { cn } from "@/lib/cn";
import ChartStage from "@/components/immersive/ChartStage";

function mapEmbedUrl(query: string): string {
  return `https://maps.google.com/maps?q=${encodeURIComponent(query)}&t=&z=13&ie=UTF8&iwloc=&output=embed`;
}

export default function ImmersiveStage() {
  const active = useImmersive((s) => s.active);
  const source = useImmersive((s) => s.source);
  const stream = useImmersive((s) => s.stream);
  const videoUrl = useImmersive((s) => s.videoUrl);
  const mapQuery = useImmersive((s) => s.mapQuery);
  const setFrameProvider = useImmersive((s) => s.setFrameProvider);

  const videoRef = useRef<HTMLVideoElement>(null);

  // Register a frame-capture function that the connection store can call
  // when stopping mic in immersive mode. Only useful for video sources;
  // the map iframe is opaque to canvas.toDataURL.
  useEffect(() => {
    if (source === "camera" || source === "screen" || source === "video") {
      setFrameProvider(() => captureFrameFromVideo(videoRef.current));
    } else {
      setFrameProvider(null);
    }
    return () => setFrameProvider(null);
  }, [source, setFrameProvider]);

  // Attach / detach the MediaStream from the <video> element.
  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    if (source === "camera" || source === "screen") {
      el.srcObject = stream ?? null;
      el.src = "";
      if (stream) void el.play().catch(() => {});
    } else if (source === "video") {
      el.srcObject = null;
      el.src = videoUrl ?? "";
      if (videoUrl) void el.play().catch(() => {});
    } else {
      el.srcObject = null;
      el.src = "";
    }
  }, [source, stream, videoUrl]);

  const mapSrc = useMemo(
    () => (source === "map" ? mapEmbedUrl(mapQuery) : "about:blank"),
    [source, mapQuery],
  );

  if (!active) return null;

  return (
    <div
      className={cn(
        "fixed inset-0 z-[3] overflow-hidden bg-black",
        source === "camera" && "src-camera",
        source === "screen" && "src-screen",
        source === "video" && "src-video",
        source === "map" && "src-map",
        source === "chart" && "src-chart",
      )}
    >
      {source === "chart" && <ChartStage />}
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        crossOrigin="anonymous"
        className={cn(
          "absolute inset-0 h-full w-full border-0 bg-black",
          source === "camera" ? "object-cover" : "object-contain",
          source === "camera" || source === "screen" || source === "video"
            ? "block"
            : "hidden",
        )}
      />
      <iframe
        title="Map"
        referrerPolicy="no-referrer-when-downgrade"
        src={mapSrc}
        className={cn(
          "absolute inset-0 h-full w-full border-0 bg-black",
          source === "map" ? "block" : "hidden",
        )}
      />
    </div>
  );
}
