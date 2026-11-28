/**
 * The secure store lint (eslint.config.js, `no-restricted-imports`): expo-secure-store is
 * opened in lib/secureStore.ts only, so every item keeps this phone's Keychain class. The
 * blocks that set their own `no-restricted-imports` (ui/, ui/overlay/, the subject libs,
 * the clipboard) each carry the ban too. Runs the real config.
 */
import { ROOT } from "@/lib/__tests__/support/sourceFiles";

type LintMessage = { line: number; ruleId: string | null };
type FlatLinter = { verify: (code: string, config: unknown, filename: string) => LintMessage[] };

// eslint-disable-next-line @typescript-eslint/no-require-imports -- eslint and its config are CommonJS, and the lib project has no @types/node
const { Linter } = require("eslint") as { Linter: new (options: { configType: "flat"; cwd: string }) => FlatLinter };
// eslint-disable-next-line @typescript-eslint/no-require-imports -- the config is CommonJS, as above
const config = require("../../eslint.config.js") as unknown;

const linter = new Linter({ configType: "flat", cwd: ROOT });

const DIRECT = 'import * as SecureStore from "expo-secure-store";\nexport const s = SecureStore;';

function flagged(file: string): boolean {
  return linter
    .verify(DIRECT, config, `${ROOT}/${file}`)
    .some((message) => message.ruleId === "no-restricted-imports");
}

describe("secure store lint", () => {
  it.each([
    "lib/auth.ts",
    "features/account/model/anything.ts",
    "components/Anything.tsx",
    "ui/controls/Anything.tsx",
    "ui/overlay/Anything.tsx",
    "lib/math/anything.ts",
    "lib/physics/anything.ts",
    "lib/chemistry/anything.ts",
    "lib/clipboard.ts",
  ])("flags expo-secure-store in %s", (file) => {
    expect(flagged(file)).toBe(true);
  });

  it.each(["lib/secureStore.ts", "lib/__tests__/auth.test.ts"])("allows it in %s", (file) => {
    expect(flagged(file)).toBe(false);
  });
});
