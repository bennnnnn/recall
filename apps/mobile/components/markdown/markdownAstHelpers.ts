import { isStandaloneUrl } from "@/lib/richBlocks";

export type AstNode = {
  key: string;
  type?: string;
  content?: string;
  attributes?: Record<string, string>;
  children?: AstNode[];
  sourceType?: string;
};

export type AstParent = {
  type: string;
  attributes?: { start?: number; class?: string };
};

export function parentHasType(parent: unknown, type: string): boolean {
  return Array.isArray(parent) && parent.some((node) => node?.type === type);
}

export function inTableCell(parent: unknown): boolean {
  return parentHasType(parent, "td") || parentHasType(parent, "th");
}

export function inTableHeader(parent: unknown): boolean {
  return parentHasType(parent, "th");
}

export function astText(node: AstNode): string {
  if (node.content) return node.content;
  return (node.children ?? []).map(astText).join("");
}

function collectHtmlInline(nodes: AstNode[] | undefined): string[] {
  const out: string[] = [];
  for (const node of nodes ?? []) {
    if (node.sourceType === "html_inline" || node.type === "html_inline") {
      if (node.content) out.push(node.content);
    }
    out.push(...collectHtmlInline(node.children));
  }
  return out;
}

function isTaskCheckboxChecked(html: string): boolean {
  return /\bchecked(?:\s|=|>|\/)/i.test(html);
}

export function taskChecked(node: AstNode): boolean | null {
  const cls = node.attributes?.class ?? "";
  if (!cls.includes("task-list-item")) return null;
  const checkbox = collectHtmlInline(node.children).find((html) =>
    html.includes("task-list-item-checkbox"),
  );
  if (!checkbox) return false;
  return isTaskCheckboxChecked(checkbox);
}

export function countTableColumns(node: AstNode): number {
  let max = 1;
  const walk = (n: AstNode) => {
    if (n.type === "tr") {
      const cells = (n.children ?? []).filter(
        (c) => c.type === "th" || c.type === "td",
      );
      if (cells.length > max) max = cells.length;
    }
    (n.children ?? []).forEach(walk);
  };
  walk(node);
  return max;
}

export function detectStandaloneLink(node: AstNode): string | null {
  const kids = node.children ?? [];
  if (kids.length === 1 && kids[0].type === "link") {
    const href = kids[0].attributes?.href;
    return href && isStandaloneUrl(href) ? href : null;
  }
  if (kids.length === 1 && kids[0].type === "text") {
    return isStandaloneUrl(kids[0].content ?? "");
  }
  return null;
}
