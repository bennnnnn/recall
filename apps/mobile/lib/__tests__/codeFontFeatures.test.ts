/**
 * The code font carries no substitution that changes what code says: no ligatures ("fi",
 * "fl") and no contextual alternates (`->` drawn as an arrow). React Native ignores
 * `fontVariant` ligature settings on iOS, so only the font file can promise it
 * (scripts/strip-code-font-ligatures.py; iOS Simulator, 2026-11-07).
 */
import { ROOT } from "./support/sourceFiles";

// @types/node is not installed; the fs shape this needs is declared here.
// eslint-disable-next-line @typescript-eslint/no-require-imports -- untyped node:fs, as support/sourceFiles does
const fs = require("node:fs") as { readFileSync: (path: string) => Uint8Array };

function featureTags(font: Uint8Array): string[] {
  const view = new DataView(font.buffer, font.byteOffset, font.byteLength);
  const tag = (at: number) => String.fromCharCode(...font.subarray(at, at + 4));
  const tables = view.getUint16(4);
  for (let i = 0; i < tables; i += 1) {
    const record = 12 + i * 16;
    if (tag(record) !== "GSUB") continue;
    const gsub = view.getUint32(record + 8);
    const featureList = gsub + view.getUint16(gsub + 6);
    const count = view.getUint16(featureList);
    return Array.from({ length: count }, (_, k) => tag(featureList + 2 + k * 6));
  }
  return [];
}

it("ships the code font without ligatures or contextual alternates", () => {
  const tags = featureTags(fs.readFileSync(`${ROOT}/assets/fonts/SpaceMono-Regular.ttf`));
  expect(tags.length).toBeGreaterThan(0);
  expect(tags.filter((t) => ["liga", "dlig", "calt", "clig", "rlig"].includes(t))).toEqual([]);
});
