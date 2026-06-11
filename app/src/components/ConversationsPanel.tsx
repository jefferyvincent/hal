import { useConnection } from "@/stores/connection";
import { useUi } from "@/stores/ui";
import { cn } from "@/lib/cn";

function formatTimestamp(seconds: number | undefined): string {
  if (!seconds) return "";
  const d = new Date(seconds * 1000);
  if (Number.isNaN(d.getTime())) return "";
  const now = new Date();
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  if (sameDay) {
    return d.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    });
  }
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

export default function ConversationsPanel() {
  const open = useUi((s) => s.conversationsOpen);
  const close = useUi((s) => s.toggleConversations);
  const conversations = useConnection((s) => s.conversations);
  const currentId = useConnection((s) => s.currentId);
  const newConversation = useConnection((s) => s.newConversation);
  const switchConversation = useConnection((s) => s.switchConversation);
  const deleteConversation = useConnection((s) => s.deleteConversation);

  if (!open) return null;

  return (
    <aside
      className={cn(
        "immersive-fade fixed left-5 top-[70px] z-[500] flex w-[320px] flex-col",
        "max-h-[50vh] border border-hal-red bg-[rgba(8,8,11,0.95)] font-mono backdrop-blur-md",
        "shadow-[0_0_30px_rgba(255,30,30,0.4)]",
      )}
    >
      <header className="flex items-center justify-between border-b border-hal-red/20 bg-hal-red/[0.04] px-3 py-2.5 text-[9px] uppercase tracking-[4px] text-hal-red">
        <span>Conversations · {conversations.length}</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void newConversation()}
            className="border border-hal-red/40 px-2 py-0.5 text-[9px] uppercase tracking-[2px] text-hal-red hover:bg-hal-red/15 hover:text-white"
          >
            + New
          </button>
          <button
            type="button"
            aria-label="Close conversations"
            onClick={close}
            className="border border-hal-red/40 px-2 py-0.5 text-[9px] uppercase tracking-[2px] text-hal-red hover:bg-hal-red/15 hover:text-white"
          >
            Close
          </button>
        </div>
      </header>

      <div
        className={cn(
          "flex flex-col overflow-y-auto py-1",
          "[scrollbar-width:auto] [scrollbar-color:rgba(255,30,30,0.55)_rgba(255,30,30,0.08)]",
        )}
      >
        {conversations.length === 0 ? (
          <div className="px-3 py-4 text-center text-[11px] text-hal-text-dim">
            (no conversations yet)
          </div>
        ) : null}

        {conversations.map((c) => {
          const active = c.id === currentId;
          return (
            <div
              key={c.id}
              role="button"
              tabIndex={0}
              onClick={() => {
                if (!active) void switchConversation(c.id);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  if (!active) void switchConversation(c.id);
                }
              }}
              className={cn(
                "relative cursor-pointer border-l-2 border-transparent py-2.5 pl-3 pr-7 transition-colors",
                "hover:bg-hal-red/[0.06]",
                active && "border-l-hal-red bg-hal-red/10",
              )}
            >
              <div className="select-text overflow-hidden text-ellipsis whitespace-nowrap text-[12px] text-hal-text">
                {c.title || "(untitled)"}
              </div>
              <div className="mt-0.5 text-[9px] tracking-[1px] text-hal-text-dim">
                {c.message_count != null ? `${c.message_count} msgs` : ""}
                {c.message_count != null && c.updated_at ? " · " : ""}
                {formatTimestamp(c.updated_at)}
              </div>
              <button
                type="button"
                aria-label={`Delete ${c.title || "conversation"}`}
                onClick={(e) => {
                  e.stopPropagation();
                  void deleteConversation(c.id);
                }}
                className={cn(
                  "absolute right-1 top-1.5 cursor-pointer px-2 py-1 text-[18px] leading-none text-hal-red transition-all",
                  "opacity-55 hover:bg-hal-red/15 hover:text-hal-red-glow hover:opacity-100",
                  active && "opacity-85",
                )}
              >
                ×
              </button>
            </div>
          );
        })}
      </div>
    </aside>
  );
}
