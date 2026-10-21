/**
 * Structural guard: code fences are read with one grammar (`lib/mdFenceScan.ts`).
 *
 * Line loops flipped a flag on every ``` line, regexes closed a fence on the first
 * ``` anywhere, and seven files wrote the closer rule out again, so a ``` shown inside
 * a ~~~ block turned the rest of a reply inside out (code-health audit DUP-03). Read
 * markers with `readFenceMarker`, walk `scanFences` / `fencedLines` / `fenceAfterLine`,
 * or close with `closesFence`.
 *
 * The lib jest project pins `types: ["jest"]` and @types/node is not installed, so the
 * node shapes this needs are declared here (as in fileLocalExports.test.ts).
 */

declare const __dirname: string;
// eslint-disable-next-line @typescript-eslint/no-require-imports
const { readdirSync, readFileSync, statSync } = require("node:fs") as {
  readdirSync: (path: string) => string[];
  readFileSync: (path: string, encoding: "utf8") => string;
  statSync: (path: string) => { isDirectory: () => boolean };
};

/** apps/mobile, spelled without ".." so test paths are recognisable. */
const ROOT = __dirname.split("/").slice(0, -2).join("/");
const SOURCE_DIRS = ["app", "components", "features", "lib", "hooks", "contexts", "ui"];
const SKIPPED_DIRS = new Set(["node_modules", "vendor"]);
const OWNER = "lib/mdFenceScan.ts";

/** `file: line` → why that line may read a fence by hand. */
const ALLOWED: Record<string, string> = {
  'lib/markdown/preprocessTables.ts: if (line.startsWith("```", i)) {':
    "drops a ```lang token left inside a table cell; no fence is read",
  "lib/math/pasteNormalize.ts: return trimmed.replace(/```math\\n([\\s\\S]*?)```/gi, (_m, body: string) => {":
    "the user's paste in the composer, where a closer glued to the last line still ends it",
};

const HAND_READS = [
  // A fence line tested by its first characters.
  /\.startsWith\(\s*["'`](?:```|~~~)/,
  // A regex anchored on a fence line: /^```/, /^(?:```|~~~)/, /^\s*```/.
  /\/\^(?:\\s\*|\[ \\t\]\*)?\(?(?:\?:)?(?:```|~~~)/,
  // A regex spanning a whole fence, which closes on the first ``` anywhere.
  /\/[^/\n]*```[^\n]*```[^\n]*\/[gimsuy]*/,
  // The closer rule written out again.
  /\.char\s*===\s*\w+\.char/,
];

function sourceFiles(dir: string): string[] {
  let names: string[];
  try {
    names = readdirSync(dir);
  } catch {
    return [];
  }
  return names.flatMap((name: string) => {
    const path = `${dir}/${name}`;
    if (statSync(path).isDirectory()) {
      return SKIPPED_DIRS.has(name) ? [] : sourceFiles(path);
    }
    return /\.tsx?$/.test(name) ? [path] : [];
  });
}

function isTest(path: string): boolean {
  return path.includes("/__tests__/") || /\.test\.tsx?$/.test(path);
}

/** The trimmed code lines (not comments) that read a fence by hand. */
function handReads(text: string): string[] {
  return text.split("\n").flatMap((line) => {
    const trimmed = line.trim();
    if (trimmed.startsWith("//") || trimmed.startsWith("*") || trimmed.startsWith("/*")) return [];
    return HAND_READS.some((pattern) => pattern.test(line)) ? [trimmed] : [];
  });
}

function productionReads(): string[] {
  return SOURCE_DIRS.flatMap((dir) => sourceFiles(`${ROOT}/${dir}`))
    .filter((file) => !isTest(file) && !file.endsWith(OWNER))
    .flatMap((file) => {
      const relative = file.slice(ROOT.length + 1);
      return handReads(readFileSync(file, "utf8")).map((line) => `${relative}: ${line}`);
    });
}

describe("one fence grammar", () => {
  it("sees a hand-written fence read", () => {
    expect(handReads('if (line.trimStart().startsWith("```")) inFence = !inFence;')).toHaveLength(1);
    expect(handReads("const FENCE = /^(?:```|~~~)/;")).toHaveLength(1);
    expect(handReads("text.replace(/```math\\n([\\s\\S]*?)```/g, '')")).toHaveLength(1);
    expect(handReads("if (marker.char === open.char) open = null;")).toHaveLength(1);
    expect(handReads("// a line that starts with ``` opens a fence")).toEqual([]);
  });

  it("no production code reads a fence by hand", () => {
    expect(productionReads().filter((entry) => !(entry in ALLOWED))).toEqual([]);
  });

  it("every allowance still applies", () => {
    const reads = new Set(productionReads());
    expect(Object.keys(ALLOWED).filter((entry) => !reads.has(entry))).toEqual([]);
  });
});
