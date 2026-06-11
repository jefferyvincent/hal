import { useEffect, useState } from "react";
import { useConnection } from "@/stores/connection";
import { useUi } from "@/stores/ui";
import { cn } from "@/lib/cn";
import type { McpStatus } from "@/types";

const STATUS_COLOR: Record<McpStatus, string> = {
  connected: "text-emerald-400",
  needs_auth: "text-hal-amber-bright",
  error: "text-hal-red",
  connecting: "text-hal-amber",
  disabled: "text-hal-text-dim",
  unknown: "text-hal-text-dim",
};

const inputCls =
  "border border-hal-red/30 bg-black/40 px-2 py-1.5 text-[12px] text-hal-text focus:border-hal-red focus:outline-none";
const labelCls = "text-[9px] uppercase tracking-[2px] text-hal-text-dim";

// Connect HAL to external MCP servers. The form posts to the server (mcp_add),
// which persists the config to SQLite, connects, and discovers the tools. The
// list reflects live connection status pushed back over the socket.
export default function McpPanel() {
  const open = useUi((s) => s.mcpOpen);
  const toggle = useUi((s) => s.toggleMcp);
  const servers = useConnection((s) => s.mcpServers);
  const listMcp = useConnection((s) => s.listMcp);
  const addMcp = useConnection((s) => s.addMcp);
  const removeMcp = useConnection((s) => s.removeMcp);
  const toggleServer = useConnection((s) => s.toggleMcpServer);
  const refreshMcp = useConnection((s) => s.refreshMcp);
  const authorizeMcp = useConnection((s) => s.authorizeMcp);

  const [name, setName] = useState("");
  const [transport, setTransport] = useState("stdio");
  const [serverCommand, setServerCommand] = useState("");
  const [args, setArgs] = useState("");
  const [url, setUrl] = useState("");
  const [env, setEnv] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [headers, setHeaders] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);

  // Pull the current server list whenever the panel opens.
  useEffect(() => {
    if (open) listMcp();
  }, [open, listMcp]);

  if (!open) return null;

  const canSubmit =
    name.trim() !== "" &&
    (transport === "stdio" ? serverCommand.trim() !== "" : url.trim() !== "");

  function submit() {
    if (!canSubmit) return;
    addMcp({
      name: name.trim(),
      transport,
      server_command: serverCommand.trim(),
      args: args.trim(),
      url: url.trim(),
      env: env.trim(),
      api_key: apiKey.trim(),
      headers: headers.trim(),
    });
    setName("");
    setServerCommand("");
    setArgs("");
    setUrl("");
    setEnv("");
    setApiKey("");
    setHeaders("");
  }

  return (
    <div
      className="fixed inset-0 z-40 flex items-start justify-center bg-black/60 backdrop-blur-sm"
      onClick={toggle}
    >
      <aside
        onClick={(e) => e.stopPropagation()}
        className={cn(
          "mt-[70px] flex max-h-[calc(100vh-140px)] w-[460px] flex-col font-mono",
          "border border-hal-red/25 bg-[rgba(8,8,11,0.96)] shadow-[0_0_40px_rgba(0,0,0,0.7)]",
        )}
      >
        <header className="flex items-center justify-between border-b border-hal-red/20 bg-hal-red/[0.04] px-3 py-2.5 text-[9px] uppercase tracking-[4px] text-hal-red">
          <span>MCP Servers · {servers.length}</span>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={refreshMcp}
              className="text-[9px] uppercase tracking-[2px] text-hal-text-dim hover:text-hal-red-glow"
            >
              Refresh
            </button>
            <button
              type="button"
              onClick={toggle}
              className="text-[9px] uppercase tracking-[2px] text-hal-text-dim hover:text-hal-red-glow"
            >
              Close
            </button>
          </div>
        </header>

        <div className="overflow-y-auto p-4 [scrollbar-color:rgba(255,30,30,0.3)_transparent] [scrollbar-width:thin]">
          {/* Add form */}
          <div className="flex flex-col gap-3 border border-hal-red/15 p-3">
            <div className="text-[9px] uppercase tracking-[3px] text-hal-amber">
              Add a server
            </div>
            <label className="flex flex-col gap-1">
              <span className={labelCls}>Name</span>
              <input
                className={inputCls}
                value={name}
                placeholder="TradeScans"
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className={labelCls}>Transport</span>
              <select
                className={inputCls}
                value={transport}
                onChange={(e) => setTransport(e.target.value)}
              >
                <option value="stdio">stdio (local command)</option>
                <option value="http">http (hosted URL)</option>
              </select>
            </label>

            {transport === "stdio" ? (
              <>
                <label className="flex flex-col gap-1">
                  <span className={labelCls}>Command</span>
                  <input
                    className={inputCls}
                    value={serverCommand}
                    placeholder="npx"
                    onChange={(e) => setServerCommand(e.target.value)}
                  />
                </label>
                <label className="flex flex-col gap-1">
                  <span className={labelCls}>Args (space-separated or JSON array)</span>
                  <input
                    className={inputCls}
                    value={args}
                    placeholder="-y @org/server-name"
                    onChange={(e) => setArgs(e.target.value)}
                  />
                </label>
                <label className="flex flex-col gap-1">
                  <span className={labelCls}>Env (KEY=VALUE per line)</span>
                  <textarea
                    className={cn(inputCls, "min-h-[52px] resize-y")}
                    value={env}
                    placeholder={"TOKEN=abc123"}
                    onChange={(e) => setEnv(e.target.value)}
                  />
                </label>
              </>
            ) : (
              <>
                <label className="flex flex-col gap-1">
                  <span className={labelCls}>URL</span>
                  <input
                    className={inputCls}
                    value={url}
                    placeholder="https://host/mcp"
                    onChange={(e) => setUrl(e.target.value)}
                  />
                </label>
                <label className="flex flex-col gap-1">
                  <span className={labelCls}>
                    API Key (paste the raw key — sent as Authorization: Bearer)
                  </span>
                  <input
                    className={inputCls}
                    value={apiKey}
                    type="password"
                    placeholder="paste your API key"
                    onChange={(e) => setApiKey(e.target.value)}
                  />
                </label>
                <label className="flex flex-col gap-1">
                  <span className={labelCls}>
                    Extra headers (optional, KEY=VALUE per line)
                  </span>
                  <textarea
                    className={cn(inputCls, "min-h-[44px] resize-y")}
                    value={headers}
                    placeholder={"apikey=abc123"}
                    onChange={(e) => setHeaders(e.target.value)}
                  />
                </label>
                <div className="text-[9px] leading-snug text-hal-text-dim">
                  Leave API Key and headers empty for servers that use a browser
                  sign-in (OAuth) — HAL will prompt you to authorize after adding.
                </div>
              </>
            )}

            <button
              type="button"
              disabled={!canSubmit}
              onClick={submit}
              className={cn(
                "mt-1 border px-3 py-1.5 text-[10px] uppercase tracking-[3px] transition-colors",
                canSubmit
                  ? "border-hal-red/60 text-hal-red hover:bg-hal-red/15"
                  : "cursor-not-allowed border-hal-text-dim/30 text-hal-text-dim/50",
              )}
            >
              Add server
            </button>
          </div>

          {/* Server list */}
          <div className="mt-4 flex flex-col gap-3">
            {servers.length === 0 ? (
              <div className="text-center text-[11px] text-hal-text-dim">
                (no MCP servers yet)
              </div>
            ) : null}

            {servers.map((s) => (
              <article key={s.id} className="border-l-2 border-l-hal-red/40 pl-2.5">
                <div className="flex items-center justify-between">
                  <div className="text-[12px] text-hal-text">{s.name}</div>
                  <div
                    className={cn(
                      "text-[9px] uppercase tracking-[2px]",
                      STATUS_COLOR[s.status] ?? "text-hal-text-dim",
                    )}
                  >
                    {s.status}
                  </div>
                </div>
                <div className="text-[9px] uppercase tracking-[2px] text-hal-text-dim">
                  {s.transport} · {s.transport === "stdio" ? s.command : s.url}
                </div>
                {s.error ? (
                  <div className="mt-1">
                    <pre className="max-h-[160px] select-text overflow-y-auto whitespace-pre-wrap break-words border-l border-hal-red/40 bg-black/40 px-2 py-1 text-[10px] leading-snug text-hal-red/90">
                      {s.error}
                    </pre>
                    <button
                      type="button"
                      onClick={() => {
                        void navigator.clipboard?.writeText(s.error ?? "");
                      }}
                      className="mt-0.5 text-[9px] uppercase tracking-[2px] text-hal-text-dim hover:text-hal-red-glow"
                    >
                      Copy error
                    </button>
                  </div>
                ) : null}

                <div className="mt-1.5 flex items-center gap-3 text-[9px] uppercase tracking-[2px]">
                  <button
                    type="button"
                    onClick={() => setExpanded(expanded === s.id ? null : s.id)}
                    className="text-hal-amber hover:text-hal-amber-bright"
                  >
                    {s.tool_count} tool{s.tool_count === 1 ? "" : "s"}
                  </button>
                  {s.transport !== "stdio" && s.status === "needs_auth" ? (
                    <button
                      type="button"
                      onClick={() => authorizeMcp(s.id)}
                      className="text-hal-amber-bright hover:text-white"
                    >
                      Authorize
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => toggleServer(s.id, !s.enabled)}
                    className="text-hal-text-dim hover:text-hal-red-glow"
                  >
                    {s.enabled ? "Disable" : "Enable"}
                  </button>
                  <button
                    type="button"
                    onClick={() => removeMcp(s.id)}
                    className="text-hal-text-dim hover:text-hal-red"
                  >
                    Remove
                  </button>
                </div>

                {expanded === s.id && s.tools.length > 0 ? (
                  <ul className="mt-1.5 flex flex-col gap-1 border-l border-hal-amber/30 pl-2">
                    {s.tools.map((t) => (
                      <li key={t.name} className="text-[10.5px] text-hal-text-dim">
                        <span className="text-hal-text">{t.name}</span>
                        {t.description ? ` — ${t.description}` : ""}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </article>
            ))}
          </div>
        </div>
      </aside>
    </div>
  );
}
