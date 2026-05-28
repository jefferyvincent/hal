// Lightweight markdown → HTML renderer, ported from the legacy index.html.
// Covers what HAL actually emits: bold, italic, inline code, headers,
// bullet lists, and fenced code blocks. No DOMPurify needed because we
// escape all HTML first and only inject our own tags.

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function applyInlineMarkdown(text: string): string {
  let s = escapeHtml(text);
  s = s.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/(?<![\*\w])\*([^*\n]+)\*(?![\*\w])/g, "<em>$1</em>");
  s = s.replace(/`([^`\n]+)`/g, "<code>$1</code>");
  return s;
}

function applyBlockMarkdown(text: string): string {
  const lines = text.split("\n");
  const out: string[] = [];
  let inList = false;
  const closeList = () => {
    if (inList) {
      out.push("</ul>");
      inList = false;
    }
  };
  for (const line of lines) {
    const bullet = line.match(/^\s*[\-\*]\s+(.+)/);
    const header = line.match(/^(#{1,4})\s+(.+)/);
    if (bullet) {
      if (!inList) {
        out.push("<ul>");
        inList = true;
      }
      out.push(`<li>${applyInlineMarkdown(bullet[1])}</li>`);
    } else if (header) {
      closeList();
      const level = Math.min(6, header[1].length + 2);
      out.push(`<h${level}>${applyInlineMarkdown(header[2])}</h${level}>`);
    } else {
      closeList();
      if (line.trim()) out.push(applyInlineMarkdown(line));
      else out.push("");
    }
  }
  closeList();
  return out.join("<br/>");
}

export interface RenderedMessage {
  /** Safe HTML for the message body. */
  html: string;
  /** Number of code blocks rendered. */
  codeBlocks: number;
}

/** Render a HAL message body to HTML. Fenced code blocks are emitted as
 *  <pre data-lang="..."><code>...</code></pre>. */
export function renderMessage(content: string): RenderedMessage {
  const parts = content.split(/(```[\s\S]*?```)/g);
  let html = "";
  let codeBlocks = 0;
  for (const part of parts) {
    if (part.startsWith("```") && part.endsWith("```")) {
      const inner = part.slice(3, -3);
      const nl = inner.indexOf("\n");
      const lang = nl >= 0 ? inner.slice(0, nl).trim() : "";
      const code = nl >= 0 ? inner.slice(nl + 1) : inner;
      html += `<pre data-lang="${escapeHtml(lang)}"><code>${escapeHtml(code)}</code></pre>`;
      codeBlocks++;
    } else if (part) {
      html += applyBlockMarkdown(part);
    }
  }
  return { html, codeBlocks };
}
