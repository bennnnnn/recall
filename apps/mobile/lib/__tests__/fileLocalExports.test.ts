/**
 * Structural guard: an export is named by some other file.
 *
 * Fifty exported types and values were read only inside their own file (#1914
 * had cleared 35 more before that). An export nothing imports reads as public
 * API, so the next change keeps it compatible for callers that do not exist.
 * Drop `export` instead; add it back when a second file needs the name.
 *
 * The lib jest project pins `types: ["jest"]` and @types/node is not
 * installed, so the node shapes this needs are declared here (as in
 * libLayout.test.ts).
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
/** Vendored code keeps upstream exports; installed packages are not ours. */
const SKIPPED_DIRS = new Set(["node_modules", "vendor"]);
/** Names Expo Router reads from a route file. */
const ROUTER_EXPORTS = new Set(["unstable_settings", "ErrorBoundary"]);

const DECLARATION =
  /^export\s+(?:declare\s+)?(?:async\s+)?(?:type|interface|const|let|function|class|enum)\s+([A-Za-z_$][\w$]*)/gm;
const WORD = /[A-Za-z_$][\w$]*/g;

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

/** Root-level config and setup files may name an export too (jest mocks, say). */
function rootFiles(): string[] {
  return readdirSync(ROOT)
    .filter((name: string) => /\.(t|j)sx?$/.test(name))
    .map((name: string) => `${ROOT}/${name}`);
}

function isTest(path: string): boolean {
  return path.includes("/__tests__/") || /\.test\.tsx?$/.test(path);
}

describe("exports", () => {
  it("every exported declaration is named in another file", () => {
    const files = SOURCE_DIRS.flatMap((dir) => sourceFiles(`${ROOT}/${dir}`));
    const texts = new Map<string, string>();
    for (const file of [...files, ...rootFiles()]) texts.set(file, readFileSync(file, "utf8"));
    const filesByWord = new Map<string, Set<string>>();
    for (const [file, text] of texts) {
      for (const word of new Set(text.match(WORD) ?? [])) {
        const named = filesByWord.get(word) ?? new Set<string>();
        named.add(file);
        filesByWord.set(word, named);
      }
    }

    const fileLocal: string[] = [];
    for (const file of files) {
      if (isTest(file)) continue;
      const relative = file.slice(ROOT.length + 1);
      for (const match of (texts.get(file) ?? "").matchAll(DECLARATION)) {
        const name = match[1];
        if (relative.startsWith("app/") && ROUTER_EXPORTS.has(name)) continue;
        const named = filesByWord.get(name) ?? new Set<string>();
        if ([...named].every((other) => other === file)) fileLocal.push(`${relative} ${name}`);
      }
    }
    expect(fileLocal).toEqual([]);
  });
});
