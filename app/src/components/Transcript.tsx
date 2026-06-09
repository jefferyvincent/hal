import { useEffect, useRef } from "react";
import { useConnection } from "@/stores/connection";
import { useUi } from "@/stores/ui";
import { renderMessage } from "@/lib/markdown";
import { cn } from "@/lib/cn";

export default function Transcript() {
  const history = useConnection((s) => s.history);
  const pendingHal = useConnection((s) => s.pendingHal);
  const fullscreen = useUi((s) => s.fullscreenChat);
  const chatOpen = useUi((s) => s.chatOpen);
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Jump to the latest message when the panel is first opened.
  useEffect(() => {
    if (chatOpen) bottomRef.current?.scrollIntoView({ block: "end" });
  }, [chatOpen]);

  // On new content, only stick to the bottom if the user is already near it —
  // so scrolling up to read history isn't yanked back down mid-reply.
  useEffect(() => {
    if (!chatOpen) return;
    const el = containerRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
    if (nearBottom) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [history, pendingHal, chatOpen]);

  if (!chatOpen) return null;

  const onCopy = (e: React.MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;
    const btn = target.closest("[data-copy]") as HTMLButtonElement | null;
    if (!btn) return;
    const pre = btn.parentElement?.querySelector("pre");
    if (!pre) return;
    navigator.clipboard
      .writeText(pre.textContent ?? "")
      .then(() => {
        btn.textContent = "Copied";
        setTimeout(() => (btn.textContent = "Copy"), 1500);
      })
      .catch(() => {
        btn.textContent = "Failed";
        setTimeout(() => (btn.textContent = "Copy"), 1500);
      });
  };

  return (
    <div
      ref={containerRef}
      className={cn(
        // Fixed positioning with a hard bottom floor at 240px keeps the
        // transcript from ever sliding under the Controls bar (which sits
        // at bottom:150 with 80px height) or the InputBar (bottom:60).
        "immersive-fade fixed left-1/2 z-[5] flex w-[min(960px,92vw)] -translate-x-1/2 flex-col gap-2 overflow-y-auto px-6 text-[13px] leading-[1.55]",
        fullscreen
          ? "top-[80px] bottom-[280px]"
          : "bottom-[280px] max-h-[46vh]",
      )}
      onClick={onCopy}
    >
      {history.length === 0 && !pendingHal ? (
        <div className="text-center text-hal-text-dim">(no messages yet)</div>
      ) : null}
      {history.map((m, i) => {
        const rendered = renderMessage(m.content);
        return (
          <div
            key={i}
            className={cn(
              "md max-w-full select-text whitespace-pre-wrap break-words rounded border-l-2 px-3 py-2",
              m.role === "user"
                ? "border-hal-red/40 bg-hal-red/[0.04] text-hal-text-dim"
                : "border-hal-amber/40 bg-hal-amber/[0.03] text-hal-text",
            )}
          >
            <div
              dangerouslySetInnerHTML={{ __html: wrapCodeBlocks(rendered.html) }}
            />
          </div>
        );
      })}
      {pendingHal ? (
        <div className="md border-l-2 border-hal-amber/40 bg-hal-amber/[0.03] px-3 py-2 text-hal-text-dim">
          <em>(HAL is composing…)</em>
        </div>
      ) : null}
      <div ref={bottomRef} />
    </div>
  );
}

/** Insert a "Copy" button into each rendered <pre> code block. */
function wrapCodeBlocks(html: string): string {
  return html.replace(
    /<pre data-lang="([^"]*)"><code>([\s\S]*?)<\/code><\/pre>/g,
    (_match, lang, code) => `
      <div class="relative my-2">
        <button data-copy class="absolute right-1 top-1 z-10 border border-hal-amber/40 bg-black/60 px-2 py-0.5 text-[10px] uppercase tracking-widest text-hal-amber hover:bg-hal-amber/20">Copy</button>
        <pre data-lang="${lang}"><code>${code}</code></pre>
      </div>`,
  );
}
