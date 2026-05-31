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

// A pipe-table row: starts/ends with optional whitespace + contains at least
// one "|". The separator row is all dashes/colons/pipes (e.g. |---|:--:|).
const TABLE_ROW = /^\s*\|(.+)\|\s*$/;
const TABLE_SEP = /^\s*\|?[\s:\-|]+\|?\s*$/;

function splitCells(row: string): string[] {
  const m = row.match(TABLE_ROW);
  const inner = m ? m[1] : row;
  return inner.split("|").map((c) => c.trim());
}

// Render a markdown pipe table to an HTML <table>. Inline styles are used so
// it renders without depending on Tailwind seeing dynamic class strings.
function renderTable(header: string, rows: string[]): string {
  const th = splitCells(header)
    .map(
      (c) =>
        `<th style="border:1px solid rgba(255,179,0,0.3);padding:4px 8px;text-align:left;color:#ffd44a;font-size:11px;text-transform:uppercase;letter-spacing:1px;">${applyInlineMarkdown(c)}</th>`,
    )
    .join("");
  const body = rows
    .map(
      (r) =>
        "<tr>" +
        splitCells(r)
          .map(
            (c) =>
              `<td style="border:1px solid rgba(255,30,30,0.2);padding:4px 8px;color:#c8c8d0;">${applyInlineMarkdown(c)}</td>`,
          )
          .join("") +
        "</tr>",
    )
    .join("");
  return `<table style="border-collapse:collapse;margin:8px 0;width:100%;font-size:12px;"><thead><tr>${th}</tr></thead><tbody>${body}</tbody></table>`;
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
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    // Table: a header row immediately followed by a separator row.
    if (
      TABLE_ROW.test(line) &&
      i + 1 < lines.length &&
      TABLE_SEP.test(lines[i + 1]) &&
      lines[i + 1].includes("|")
    ) {
      closeList();
      const header = line;
      const body: string[] = [];
      let j = i + 2;
      while (j < lines.length && TABLE_ROW.test(lines[j])) {
        body.push(lines[j]);
        j++;
      }
      out.push(renderTable(header, body));
      i = j - 1;
      continue;
    }
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
