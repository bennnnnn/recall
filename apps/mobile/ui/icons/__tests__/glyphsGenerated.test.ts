import { GLYPHS } from "../glyphs.generated";
import manifest from "../manifest.json";

// The test project includes Jest types, but no global Node type package.
declare const __dirname: string;
const { readFileSync } = jest.requireActual<{
  readFileSync(path: string, encoding: "utf8"): string;
}>("node:fs");
const { join } = jest.requireActual<{ join(...parts: string[]): string }>("node:path");

// glyphs.generated.ts is built by `pnpm icons` from the installed lucide-static, and nothing
// else runs it: a Lucide bump that renames an id the manifest uses (1.70 renamed circle-alert
// and triangle-alert) would leave the manifest pointing at nothing until the next run failed.
const lucideDir = join(__dirname, "..", "..", "..", "node_modules", "lucide-static");
const iconNodes = JSON.parse(readFileSync(join(lucideDir, "icon-nodes.json"), "utf8")) as Record<
  string,
  unknown
>;
const lucideVersion = (
  JSON.parse(readFileSync(join(lucideDir, "package.json"), "utf8")) as { version: string }
).version;
const icons = manifest.icons as Record<string, string>;

describe("glyphs.generated.ts", () => {
  it.each(Object.entries(icons))("finds %s (Lucide %s) in the installed Lucide", (_name, id) => {
    expect(iconNodes[id]).toBeDefined();
  });

  it.each(Object.entries(icons))("draws %s as Lucide's %s", (name, id) => {
    expect(GLYPHS[name as keyof typeof GLYPHS]).toEqual(iconNodes[id]);
  });

  it("was built from the installed Lucide version", () => {
    const source = readFileSync(join(__dirname, "..", "glyphs.generated.ts"), "utf8");
    expect(source).toContain(`Drawings: Lucide v${lucideVersion} `);
  });
});
