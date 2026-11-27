/**
 * Every package with native code is pinned to one exact version. A build's native code
 * is what its packages were when it was built; with a range (`^1.2.0`, `~1.2.0`) a
 * lockfile refresh can move one, and the next store build or over-the-air update quietly
 * carries different native code from the one tested. A JavaScript-only package may keep
 * its range. Native here means an iOS or Android folder, a podspec, an Expo module or an
 * Expo config plugin.
 */
declare const __dirname: string;

const { join } = jest.requireActual<{ join(...parts: string[]): string }>("node:path");
const fs = jest.requireActual<{
  existsSync(path: string): boolean;
  readdirSync(path: string): string[];
}>("node:fs");

const ROOT = join(__dirname, "..", "..");
const pkg = jest.requireActual<{
  dependencies: Record<string, string>;
  devDependencies: Record<string, string>;
}>(join(ROOT, "package.json"));

const NATIVE_MARKERS = ["ios", "android", "app.plugin.js", "expo-module.config.json"];

function isNative(name: string): boolean {
  const dir = join(ROOT, "node_modules", name);
  if (!fs.existsSync(dir)) return false;
  return (
    NATIVE_MARKERS.some((marker) => fs.existsSync(join(dir, marker))) ||
    fs.readdirSync(dir).some((file) => file.endsWith(".podspec"))
  );
}

const EXACT = /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/;

it("pins every package with native code to an exact version", () => {
  const all = { ...pkg.dependencies, ...pkg.devDependencies };
  const native = Object.keys(all).filter(isNative);
  // The check sees the installed packages: an empty list would pass anything.
  expect(native).toEqual(expect.arrayContaining(["expo", "react-native", "@sentry/react-native"]));
  expect(native.filter((name) => !EXACT.test(all[name])).map((name) => `${name}@${all[name]}`)).toEqual([]);
});
