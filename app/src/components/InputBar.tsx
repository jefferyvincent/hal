import { useEffect, useRef, useState } from "react";
import { useConnection } from "@/stores/connection";
import { useAttachments } from "@/stores/attachments";
import { cn } from "@/lib/cn";
import CameraModal from "./CameraModal";

export default function InputBar() {
  const sendText = useConnection((s) => s.sendText);
  const items = useAttachments((s) => s.items);
  const addAttachment = useAttachments((s) => s.add);
  const removeAttachment = useAttachments((s) => s.remove);
  const clearAttachments = useAttachments((s) => s.clear);
  const error = useAttachments((s) => s.error);

  const [text, setText] = useState("");
  const [dragging, setDragging] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const dragDepth = useRef(0);

  // Window-level drag-drop: any file dropped on the app becomes an attachment.
  useEffect(() => {
    const onDragEnter = (e: DragEvent) => {
      if (!e.dataTransfer?.types?.includes("Files")) return;
      e.preventDefault();
      dragDepth.current++;
      setDragging(true);
    };
    const onDragOver = (e: DragEvent) => {
      if (!e.dataTransfer?.types?.includes("Files")) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
    };
    const onDragLeave = (e: DragEvent) => {
      if (!e.dataTransfer?.types?.includes("Files")) return;
      e.preventDefault();
      dragDepth.current = Math.max(0, dragDepth.current - 1);
      if (dragDepth.current === 0) setDragging(false);
    };
    const onDrop = (e: DragEvent) => {
      e.preventDefault();
      dragDepth.current = 0;
      setDragging(false);
      const files = Array.from(e.dataTransfer?.files ?? []);
      for (const f of files) void addAttachment(f);
    };
    window.addEventListener("dragenter", onDragEnter);
    window.addEventListener("dragover", onDragOver);
    window.addEventListener("dragleave", onDragLeave);
    window.addEventListener("drop", onDrop);
    return () => {
      window.removeEventListener("dragenter", onDragEnter);
      window.removeEventListener("dragover", onDragOver);
      window.removeEventListener("dragleave", onDragLeave);
      window.removeEventListener("drop", onDrop);
    };
  }, [addAttachment]);

  const submit = async () => {
    if (!text.trim() && items.length === 0) return;
    const payload = items.slice();
    const body = text;
    setText("");
    clearAttachments();
    await sendText(body, payload);
  };

  const onPickFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    for (const f of files) void addAttachment(f);
    e.target.value = "";
  };

  return (
    <>
      {dragging ? (
        <div className="pointer-events-none fixed inset-0 z-[200] flex items-center justify-center border-4 border-dashed border-hal-red bg-hal-red/10 font-display text-[18px] uppercase tracking-[8px] text-hal-red-glow backdrop-blur-sm">
          Drop to attach
        </div>
      ) : null}

      <div className="immersive-fade fixed bottom-[60px] left-1/2 z-20 flex w-[min(560px,92vw)] -translate-x-1/2 flex-col gap-2">
        {error ? (
          <div className="border border-hal-amber/40 bg-hal-amber/10 px-3 py-1 text-[10px] uppercase tracking-[2px] text-hal-amber">
            {error}
          </div>
        ) : null}

        {items.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {items.map((a, i) => (
              <span
                key={i}
                className="inline-flex max-w-[240px] items-center gap-2 border border-hal-red/30 bg-hal-red/[0.08] px-2 py-1 text-[10px] tracking-[1px] text-hal-text"
              >
                <span className="text-[9px] uppercase tracking-[2px] text-hal-amber">
                  {a.kind}
                </span>
                <span className="select-text overflow-hidden text-ellipsis whitespace-nowrap">
                  {a.name}
                </span>
                <button
                  type="button"
                  aria-label={`Remove ${a.name}`}
                  onClick={() => removeAttachment(i)}
                  className="px-0.5 font-bold text-hal-red hover:text-hal-red-glow"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        ) : null}

        <form
          className="flex w-full gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <input
            ref={fileRef}
            type="file"
            multiple
            hidden
            onChange={onPickFiles}
          />
          <button
            type="button"
            title="Attach file"
            onClick={() => fileRef.current?.click()}
            className="border border-hal-red/30 bg-hal-red/[0.06] px-3.5 font-display text-[14px] leading-none text-hal-red transition-colors hover:border-hal-red hover:bg-hal-red/15 hover:text-white"
          >
            +
          </button>
          <button
            type="button"
            title="Snap a photo to attach"
            onClick={() => setCameraOpen(true)}
            className="flex items-center justify-center border border-hal-red/30 bg-hal-red/[0.06] px-3 text-hal-red transition-colors hover:border-hal-red hover:bg-hal-red/15 hover:text-white"
          >
            <svg
              className="h-4 w-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
              <circle cx="12" cy="13" r="4" />
            </svg>
          </button>
          <input
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="TYPE DIRECTIVE…"
            className={cn(
              "flex-1 select-text border border-hal-red/25 bg-hal-red/[0.04] px-3.5 py-2.5 font-mono text-[12px] tracking-[1px] text-hal-text caret-hal-red outline-none",
              "placeholder:tracking-[3px] placeholder:text-hal-text-dim/60",
              "focus:border-hal-red focus:bg-hal-red/[0.08] focus:text-white focus:shadow-[0_0_24px_rgba(255,30,30,0.25)]",
            )}
          />
          <button
            type="submit"
            disabled={!text.trim() && items.length === 0}
            className="border border-hal-red/30 bg-hal-red/[0.06] px-4 font-display text-[10px] uppercase tracking-[4px] text-hal-red transition-colors hover:border-hal-red hover:bg-hal-red/15 hover:text-white disabled:cursor-not-allowed disabled:opacity-30"
          >
            Send
          </button>
        </form>
      </div>

      <CameraModal
        open={cameraOpen}
        onClose={() => setCameraOpen(false)}
        onSnap={() => {
          if (!text.trim()) setText("What do you see?");
        }}
      />
    </>
  );
}
