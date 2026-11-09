/**
 * The render-refs lint (eslint.config.js, `react-hooks/refs`), on the whole app. It was on
 * for features/chat only, and 26 hooks elsewhere wrote "the latest value" into a ref while
 * rendering, beside the one `useLatestRef` that does it once the render commits. Runs the
 * real config.
 */
import { ROOT } from "@/lib/__tests__/support/sourceFiles";

type LintMessage = { line: number; ruleId: string | null };
type FlatLinter = { verify: (code: string, config: unknown, filename: string) => LintMessage[] };

// eslint-disable-next-line @typescript-eslint/no-require-imports -- eslint and its config are CommonJS, and the lib project has no @types/node
const { Linter } = require("eslint") as { Linter: new (options: { configType: "flat"; cwd: string }) => FlatLinter };
// eslint-disable-next-line @typescript-eslint/no-require-imports -- the config is CommonJS, as above
const config = require("../../eslint.config.js") as unknown;

const linter = new Linter({ configType: "flat", cwd: ROOT });

function flagged(code: string, file: string): number[] {
  return linter
    .verify(code, config, `${ROOT}/${file}`)
    .filter((message) => message.ruleId === "react-hooks/refs")
    .map((message) => message.line);
}

const WRITTEN_IN_RENDER = [
  'import { useCallback, useRef } from "react";',
  "export function useDemo(onDone: () => void) {",
  "  const latest = useRef(onDone);",
  "  latest.current = onDone;",
  "  return useCallback(() => latest.current(), []);",
  "}",
].join("\n");

const LATEST_REF = [
  'import { useCallback } from "react";',
  'import { useLatestRef } from "@/lib/latestRef";',
  "export function useDemo(onDone: () => void) {",
  "  const latest = useLatestRef(onDone);",
  "  return useCallback(() => latest.current(), [latest]);",
  "}",
].join("\n");

describe("render refs lint", () => {
  it.each([
    "features/todos/hooks/useDemo.ts",
    "features/chat/hooks/useDemo.ts",
    "hooks/useDemo.ts",
    "ui/share/useDemo.ts",
    "components/rich/useDemo.ts",
    "lib/useDemo.ts",
  ])("flags a ref written while rendering in %s", (file) => {
    expect(flagged(WRITTEN_IN_RENDER, file)).toEqual([4]);
  });

  it("leaves useLatestRef and tests alone", () => {
    expect(flagged(LATEST_REF, "features/todos/hooks/useDemo.ts")).toEqual([]);
    expect(flagged(WRITTEN_IN_RENDER, "features/todos/hooks/__tests__/useDemo.test.ts")).toEqual([]);
  });
});
