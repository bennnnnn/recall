import { appFiles, isTest, readSource, relative, ROOT } from "./support/sourceFiles";

/**
 * Every `accessibilityRole` the app sets is one Android accepts. Android throws "Invalid
 * accessibility role value" for any other, while iOS ignores it, so a sheet with
 * `accessibilityRole="dialog"` broke attach, voice, live talk, To-do and Upgrade on Android
 * only (Galaxy S23, 2026-11-07). An ARIA role Android lacks here goes on `role` instead.
 */
const DELEGATE = `${ROOT}/node_modules/react-native/ReactAndroid/src/main/java/com/facebook/react/uimanager/ReactAccessibilityDelegate.kt`;

function androidRoles(): Set<string> {
  const source = readSource(DELEGATE);
  const start = source.indexOf("public enum class AccessibilityRole");
  const body = source.slice(start, source.indexOf(";", start));
  return new Set([...body.matchAll(/\b([A-Z][A-Z_]+)\b/g)].map((m) => m[1].toLowerCase()));
}

it("sets only accessibility roles Android accepts", () => {
  const allowed = androidRoles();
  expect(allowed.has("button")).toBe(true);
  const invalid = appFiles()
    .filter((file) => !isTest(file))
    .flatMap((file) =>
      [...readSource(file).matchAll(/accessibilityRole[=:]\s*\{?\s*["']([A-Za-z_]+)["']/g)]
        .filter((m) => !allowed.has(m[1].toLowerCase()))
        .map((m) => `${relative(file)}: ${m[1]}`),
    );
  expect(invalid).toEqual([]);
});
