/**
 * Structural guard: an export is named by some other file.
 *
 * Fifty exported types and values were read only inside their own file (#1914
 * had cleared 35 more before that). An export nothing imports reads as public
 * API, so the next change keeps it compatible for callers that do not exist.
 * Drop `export` instead; add it back when a second file needs the name.
 *
 * A test is not a caller. It may import what its file also uses (a step of the
 * file's work, tested on its own); production code that only tests run is dead,
 * as lib/math/latexLeaks.ts was (now test support) and a dozen constants and resets
 * were. A seam only tests call (resetting a module's state, standing in a renderer)
 * says so in its name: `…ForTest`.
 */

import { appFiles, isTest, readSource, relative, rootFiles } from "@/lib/__tests__/support/sourceFiles";

/** Names Expo Router reads from a route file. */
const ROUTER_EXPORTS = new Set(["unstable_settings", "ErrorBoundary"]);

const DECLARATION =
  /^export\s+(?:declare\s+)?(?:async\s+)?(?:type|interface|const|let|function|class|enum)\s+([A-Za-z_$][\w$]*)/gm;
/** `export const { get: getX, set: setX } = pref;`: the names after each colon, or bare. */
const DESTRUCTURED = /^export\s+const\s+\{([^}]*)\}\s*=/gm;
const WORD = /[A-Za-z_$][\w$]*/g;
const TEST_SEAM = /ForTest$/;

function exportedNames(text: string): string[] {
  const names = [...text.matchAll(DECLARATION)].map((match) => match[1] ?? "");
  for (const match of text.matchAll(DESTRUCTURED)) {
    for (const part of (match[1] ?? "").replace(/\/\*[\s\S]*?\*\//g, "").split(",")) {
      const name = part.split(":").at(-1)?.trim();
      if (name) names.push(name);
    }
  }
  return names;
}

/** How often `name` appears in `text` as a whole word. */
function mentions(text: string, name: string): number {
  return (text.match(WORD) ?? []).filter((word) => word === name).length;
}

describe("exports", () => {
  it("every exported declaration is named in another file, and not by tests alone", () => {
    const files = appFiles();
    const texts = new Map<string, string>();
    for (const file of [...files, ...rootFiles()]) texts.set(file, readSource(file));
    const productionFilesByWord = new Map<string, Set<string>>();
    const testWords = new Set<string>();
    for (const [file, text] of texts) {
      const words = new Set(text.match(WORD) ?? []);
      if (isTest(file)) {
        for (const word of words) testWords.add(word);
        continue;
      }
      for (const word of words) {
        const named = productionFilesByWord.get(word) ?? new Set<string>();
        named.add(file);
        productionFilesByWord.set(word, named);
      }
    }

    const fileLocal: string[] = [];
    const testOnly: string[] = [];
    for (const file of files) {
      if (isTest(file)) continue;
      const path = relative(file);
      const text = texts.get(file) ?? "";
      // A declaration file describes the JavaScript beside it, which uses its names; that
      // module names each where it defines it and in module.exports.
      const javascript = file.endsWith(".d.ts");
      const own = javascript ? readSource(file.replace(/\.d\.ts$/, ".js")) : text;
      const declared = javascript ? 2 : 1;
      for (const name of exportedNames(text)) {
        if (path.startsWith("app/") && ROUTER_EXPORTS.has(name)) continue;
        const named = productionFilesByWord.get(name) ?? new Set<string>();
        if ([...named].some((other) => other !== file)) continue;
        if (!testWords.has(name)) fileLocal.push(`${path} ${name}`);
        else if (mentions(own, name) <= declared && !TEST_SEAM.test(name)) {
          testOnly.push(`${path} ${name}`);
        }
      }
    }
    expect(fileLocal).toEqual([]);
    expect(testOnly).toEqual([]);
  });
});
