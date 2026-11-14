/**
 * vendor/ holds patched copies of packages the install hands to a dependency (a package.json
 * override pointing at file:vendor/<name>). Once no dependency asks for one any more, the
 * override installs nothing, but the copy stays in the repository: code nothing runs that code
 * scanning still reads and someone still has to keep patched (image-size stayed after Metro
 * 0.87 dropped it for its own reader). So each copy must be one the lockfile resolves.
 */

// The lib test project has Jest types but no Node types (see lib/vendor/__tests__/vendor.test.ts).
declare const __dirname: string;
const { readdirSync, readFileSync } = jest.requireActual<{
  readdirSync(path: string): string[];
  readFileSync(path: string, encoding: "utf8"): string;
}>("node:fs");
const { join } = jest.requireActual<{ join(...parts: string[]): string }>("node:path");

const root = join(__dirname, "..", "..");
const lockfile = readFileSync(join(root, "pnpm-lock.yaml"), "utf8");
const vendored = readdirSync(join(root, "vendor")).filter((name) => !name.startsWith("."));

it("vendors at least one package, so the check below reads something", () => {
  expect(vendored.length).toBeGreaterThan(0);
});

it.each(vendored)("vendor/%s is installed for a dependency that needs it", (name) => {
  // A resolved copy is a package entry in the lockfile, keyed by its directory.
  expect(lockfile).toContain(`\n  ${name}@file:vendor/${name}:\n`);
});
