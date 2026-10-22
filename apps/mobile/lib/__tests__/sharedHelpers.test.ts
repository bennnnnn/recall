/**
 * Structural guard: small helpers the phone had copied keep one home (code-health audit
 * DUP-13). Six callers read a cancel their own way, three diagram parsers each kept a
 * validator kit for the server's limits, and two placed labels with their own overlap.
 */

import { appFiles, isTest, readSource, relative } from "@/lib/__tests__/support/sourceFiles";

const ONE_HOME: [string, RegExp, string][] = [
  ["reading a cancel by its name", /\.name\s*===?\s*["'](?:AbortError|CanceledError)["']/, "lib/api/abort.ts"],
  ["a fence parser's refusal error", /class \w+ extends Error \{\}/, "lib/fenceValidate.ts"],
  ["boxesOverlap", /function boxesOverlap\(/, "lib/physics/boxes.ts"],
];

describe("shared helpers", () => {
  it.each(ONE_HOME)("%s lives only in its home", (_what, pattern, home) => {
    const found = appFiles()
      .filter((file) => !isTest(file) && pattern.test(readSource(file)))
      .map(relative);
    expect(found).toEqual([home]);
  });
});
