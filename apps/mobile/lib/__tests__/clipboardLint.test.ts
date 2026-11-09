/**
 * The clipboard lint (eslint.config.js, `no-restricted-imports`): the clipboard is written
 * in lib/clipboard.ts only. The Mermaid editor link, Gmail compose and the copy hook each
 * called expo-clipboard themselves. Runs the real config.
 */
import { ROOT } from "@/lib/__tests__/support/sourceFiles";

type LintMessage = { line: number; ruleId: string | null };
type FlatLinter = { verify: (code: string, config: unknown, filename: string) => LintMessage[] };

// eslint-disable-next-line @typescript-eslint/no-require-imports -- eslint and its config are CommonJS, and the lib project has no @types/node
const { Linter } = require("eslint") as { Linter: new (options: { configType: "flat"; cwd: string }) => FlatLinter };
// eslint-disable-next-line @typescript-eslint/no-require-imports -- the config is CommonJS, as above
const config = require("../../eslint.config.js") as unknown;

const linter = new Linter({ configType: "flat", cwd: ROOT });

const DIRECT = 'import * as Clipboard from "expo-clipboard";\nexport const c = Clipboard;';

function flagged(file: string): boolean {
  return linter
    .verify(DIRECT, config, `${ROOT}/${file}`)
    .some((message) => message.ruleId === "no-restricted-imports");
}

describe("clipboard lint", () => {
  it.each([
    "components/rich/MermaidBlock.tsx",
    "features/drafts/model/openGmailCompose.ts",
    "ui/share/useCopyText.ts",
    "ui/overlay/Sheet.tsx",
  ])("flags expo-clipboard in %s", (file) => {
    expect(flagged(file)).toBe(true);
  });

  it.each(["lib/clipboard.ts", "components/__tests__/CopyButton.test.tsx"])("allows it in %s", (file) => {
    expect(flagged(file)).toBe(false);
  });
});
