/**
 * The title a Mermaid card shows: the kind of diagram its source declares
 * ("Sequence diagram", "Flowchart"), or plain "Diagram" for a kind without
 * its own name. The tool's name is not something a reader needs.
 */

/** The declaration keyword (its first word) → the title's i18n key. */
const KIND_KEYS: Record<string, string> = {
  graph: "rich.mermaid_kind_flowchart",
  flowchart: "rich.mermaid_kind_flowchart",
  "flowchart-elk": "rich.mermaid_kind_flowchart",
  sequencediagram: "rich.mermaid_kind_sequence",
  erdiagram: "rich.mermaid_kind_er",
  classdiagram: "rich.mermaid_kind_class",
  "classdiagram-v2": "rich.mermaid_kind_class",
  statediagram: "rich.mermaid_kind_state",
  "statediagram-v2": "rich.mermaid_kind_state",
  gantt: "rich.mermaid_kind_gantt",
  pie: "rich.mermaid_kind_pie",
  mindmap: "rich.mermaid_kind_mindmap",
  timeline: "rich.mermaid_kind_timeline",
};

/** The first line that declares something: front matter, `%%` comments and directives skipped. */
function declarationLine(source: string): string {
  let inFrontMatter = false;
  for (const raw of source.split("\n")) {
    const line = raw.trim();
    if (line === "---") {
      inFrontMatter = !inFrontMatter;
      continue;
    }
    if (inFrontMatter || !line || line.startsWith("%%")) continue;
    return line;
  }
  return "";
}

/** The i18n key of the card title for this diagram source. */
export function mermaidTitleKey(source: string): string {
  const keyword = declarationLine(source).split(/[\s;:]/)[0]?.toLowerCase() ?? "";
  return KIND_KEYS[keyword] ?? "rich.diagram";
}

// A node's shown text: inside [ ], ( ), { }, or quotes, as flowcharts, mind maps and
// state diagrams write it. Nested shapes ([( … )]) leave their inner brackets, trimmed below.
const NODE_TEXT = /\[([^\]\n]{1,80})\]|\(([^()\n]{1,80})\)|\{([^{}\n]{1,80})\}|"([^"\n]{1,80})"/g;
// Who takes part in a sequence diagram, and a chart's or a section's title.
const NAMED_LINE = /^(?:participant|actor|title|section)\s+(.+?)(?:\s+as\s+(.+))?$/i;
const MAX_PARTS = 12;

/**
 * What a screen reader is told a Mermaid diagram shows: the texts its source names, in
 * order, once each ("Start, Is it raining?, Take an umbrella"). The WebView it draws in
 * has no text a reader can reach (GFX-02, 2026-11-13). Empty when the source names none.
 */
export function mermaidSpokenParts(source: string): string {
  const parts: string[] = [];
  const add = (raw: string | undefined) => {
    const text = (raw ?? "").replace(/^[[({"'/\\>]+|[\])}"'/\\]+$/g, "").trim();
    if (text && !parts.includes(text) && parts.length < MAX_PARTS) parts.push(text);
  };
  const declaration = declarationLine(source);
  let declared = false;
  for (const raw of source.split("\n")) {
    const line = raw.trim();
    if (!declared) {
      declared = line === declaration;
      continue;
    }
    if (!line || line.startsWith("%%")) continue;
    const named = NAMED_LINE.exec(line);
    if (named) {
      add(named[2] ?? named[1]);
      continue;
    }
    for (const match of line.matchAll(NODE_TEXT)) add(match[1] ?? match[2] ?? match[3] ?? match[4]);
  }
  return parts.join(", ");
}
