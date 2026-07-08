/**
 * Fence-language detection and HTML-preview classification — pure, no
 * Prism dependency. Kept separate from lib/codeTokenize.ts (which imports
 * Prism and registers ~47 grammars at module load) so that rendering a
 * message with zero or non-code fences never pays that cost. Prism is
 * dynamically imported by CodeBlock.tsx only when a code fence actually
 * needs to be tokenized.
 */

export type HighlightToken = { text: string; color: string };

export const TOKEN_COLORS = {
  plain: "#2D2D2D",
  comment: "#8B8B8B",
  string: "#059669",
  number: "#2563EB",
  keyword: "#DC2626",
  function: "#7C3AED",
  className: "#0891B2",
  operator: "#64748B",
  builtin: "#EA580C",
  variable: "#CA8A04",
  tag: "#059669",
} as const;

export const LANG_TO_PRISM: Record<string, string> = {
  javascript: "javascript",
  js: "javascript",
  jsx: "jsx",
  typescript: "typescript",
  ts: "typescript",
  tsx: "tsx",
  python: "python",
  py: "python",
  bash: "bash",
  sh: "bash",
  shell: "bash",
  zsh: "bash",
  json: "json",
  sql: "sql",
  go: "go",
  golang: "go",
  rust: "rust",
  rs: "rust",
  java: "java",
  css: "css",
  scss: "scss",
  html: "markup",
  xml: "markup",
  markup: "markup",
  svg: "markup",
  yaml: "yaml",
  yml: "yaml",
  markdown: "markdown",
  md: "markdown",
  ruby: "ruby",
  rb: "ruby",
  swift: "swift",
  kotlin: "kotlin",
  kt: "kotlin",
  kts: "kotlin",
  c: "c",
  cpp: "cpp",
  "c++": "cpp",
  csharp: "csharp",
  "c#": "csharp",
  cs: "csharp",
  php: "php",
  docker: "docker",
  dockerfile: "docker",
  graphql: "graphql",
  gql: "graphql",
  diff: "diff",
  patch: "diff",
  lua: "lua",
  dart: "dart",
  r: "r",
  powershell: "powershell",
  ps1: "powershell",
  pwsh: "powershell",
  nginx: "nginx",
  toml: "toml",
  ini: "ini",
  env: "ini",
  makefile: "makefile",
  make: "makefile",
  objc: "objectivec",
  "objective-c": "objectivec",
  objectivec: "objectivec",
  scala: "scala",
  elixir: "elixir",
  ex: "elixir",
  haskell: "haskell",
  hs: "haskell",
  latex: "latex",
  tex: "latex",
  vue: "markup",
  svelte: "markup",
  code: "clike",
  plaintext: "clike",
  react: "jsx",
  "react-native": "jsx",
  rn: "jsx",
  expo: "javascript",
  node: "javascript",
  express: "javascript",
  prisma: "sql",
  proto: "protobuf",
  protobuf: "protobuf",
  tf: "hcl",
  hcl: "hcl",
  terraform: "hcl",
  vim: "vim",
  perl: "perl",
  pl: "perl",
  matlab: "matlab",
  m: "matlab",
  arduino: "cpp",
  arduino_cpp: "cpp",
  terminal: "bash",
  shellsession: "bash",
  console: "bash",
  cmd: "bash",
  prompt: "bash",
  log: "clike",
  logs: "clike",
};

export function parseFenceLang(info: string): string {
  const raw = info.trim();
  if (!raw) return "";
  const first = raw.split(/\s+/)[0] ?? "";
  return first.replace(/[{:[].*$/, "").toLowerCase();
}

export function normalizeLang(lang: string): string {
  const raw = parseFenceLang(lang);
  if (!raw) return "";
  return LANG_TO_PRISM[raw] ?? raw;
}

export function groupTokensByLine(tokens: HighlightToken[]): HighlightToken[][] {
  const lines: HighlightToken[][] = [[]];
  for (const token of tokens) {
    const parts = token.text.split("\n");
    for (let i = 0; i < parts.length; i++) {
      if (i > 0) lines.push([]);
      if (parts[i].length > 0) {
        lines[lines.length - 1].push({ text: parts[i], color: token.color });
      }
    }
  }
  if (lines.length === 1 && lines[0].length === 0) return [[]];
  return lines;
}

const HIDDEN_LANG_BADGES = new Set(["", "clike", "plain", "text", "code"]);

export function displayLang(lang: string): string {
  const trimmed = lang.trim().toLowerCase();
  if (HIDDEN_LANG_BADGES.has(trimmed)) return "";
  return trimmed;
}

/** True for ```html / ```htm / ```markup fences. */
export function isHtmlFenceLang(lang: string): boolean {
  const l = lang.trim().toLowerCase();
  return l === "html" || l === "htm" || l === "markup";
}

/** True when fence content looks like a renderable HTML page or fragment. */
export function looksLikeHtmlPage(code: string): boolean {
  const sample = code.trim().slice(0, 800);
  if (/^\s*<!DOCTYPE\s+html/i.test(sample)) return true;
  if (/^\s*<html[\s>]/i.test(sample)) return true;
  if (/^\s*<head[\s>]/i.test(sample)) return true;
  if (/^\s*<style[\s>]/i.test(sample) && /<\/style>/i.test(code)) return true;
  if (/^\s*<body[\s>]/i.test(sample)) return true;
  if (
    /<(?:html|head|body|div|section|main|form|table|style|script)[\s>]/i.test(
      sample,
    ) &&
    /<\/(?:html|body|div|section|main|form|table|script)>/i.test(code)
  ) {
    return true;
  }
  return false;
}

/** Web preview UI — only for HTML fences, not JS/JSX/Python with angle brackets. */
export function shouldUseHtmlPreview(lang: string, content: string): boolean {
  if (isHtmlFenceLang(lang)) return true;
  const l = lang.trim().toLowerCase();
  if (l && l !== "plain" && l !== "text" && l !== "clike") return false;
  return looksLikeHtmlPage(content);
}
