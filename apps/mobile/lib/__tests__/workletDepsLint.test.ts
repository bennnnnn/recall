/**
 * The worklet lint (eslint.config.js, `recall/no-worklet-deps`): a dependency array handed
 * to a Reanimated hook does nothing on native and logs "[Reanimated] Dependencies should
 * only be used on the web" in a dev build, sixteen of them at once on the chat screen.
 * The worklet's closure is its dependencies. Runs the real config.
 */
import { ROOT } from "@/lib/__tests__/support/sourceFiles";

type LintMessage = { line: number; ruleId: string | null };
type FlatLinter = { verify: (code: string, config: unknown, filename: string) => LintMessage[] };

// eslint-disable-next-line @typescript-eslint/no-require-imports -- eslint and its config are CommonJS, and the lib project has no @types/node
const { Linter } = require("eslint") as { Linter: new (options: { configType: "flat"; cwd: string }) => FlatLinter };
// eslint-disable-next-line @typescript-eslint/no-require-imports -- the config is CommonJS, as above
const config = require("../../eslint.config.js") as unknown;

const linter = new Linter({ configType: "flat", cwd: ROOT });

function flagged(code: string, file = "features/demo/components/Demo.tsx"): number[] {
  return linter
    .verify(code, config, `${ROOT}/${file}`)
    .filter((message) => message.ruleId === "recall/no-worklet-deps")
    .map((message) => message.line);
}

describe("worklet deps lint", () => {
  it.each(["features/demo/components/Demo.tsx", "hooks/useDemo.ts", "ui/hooks/useDemo.ts", "lib/math/demo.ts"])(
    "flags a dependency array on every Reanimated hook in %s",
    (file) => {
      const code = [
        "const a = useAnimatedStyle(() => ({ opacity: o.value }), [o]);",
        "const b = useDerivedValue(() => v.value * 2, [v]);",
        "const c = useAnimatedProps(() => ({ r: r.value }), []);",
        "const d = useAnimatedScrollHandler({ onScroll: () => {} }, [x]);",
        "useAnimatedReaction(() => v.value, (n) => { w.value = n; }, [w]);",
      ].join("\n");
      expect(flagged(code, file)).toEqual([1, 2, 3, 4, 5]);
    },
  );

  it("leaves the hooks without one alone", () => {
    const code = [
      "const a = useAnimatedStyle(() => ({ opacity: o.value }));",
      "const b = useDerivedValue(() => v.value * 2);",
      "useAnimatedReaction(() => v.value, (n) => { w.value = n; });",
      "const m = useMemo(() => v * 2, [v]);",
    ].join("\n");
    expect(flagged(code)).toEqual([]);
  });
});
