/** What metro.config.js adds to the bundle and what it leaves out. */
declare const __dirname: string;

type Resolution = { type: string; filePath?: string };
type ResolveRequest = (
  context: Record<string, unknown>,
  moduleName: string,
  platform: string | null,
) => Resolution;
type MetroConfig = { resolver: { assetExts: string[]; resolveRequest: ResolveRequest } };

const { join } = jest.requireActual<{ join(...parts: string[]): string }>("node:path");
// eslint-disable-next-line @typescript-eslint/no-require-imports -- the CommonJS config Metro loads
const config = require(join(__dirname, "..", "..", "metro.config.js")) as MetroConfig;

/** Resolves as Metro would for one bundle; the app's own resolver hands anything else on. */
function resolve(
  moduleName: string,
  { platform = "ios", dev = false, from = "/app/lib/purchases.ts" } = {},
): Resolution {
  const context = {
    dev,
    originModulePath: from,
    resolveRequest: (_context: unknown, name: string) => ({ type: "sourceFile", filePath: name }),
  };
  return config.resolver.resolveRequest(context, moduleName, platform);
}

const EMPTY = { type: "empty" };

describe("metro.config.js", () => {
  it("ships the preview WebViews' libraries (lib/vendor/*.txt) as assets", () => {
    expect(config.resolver.assetExts).toContain("txt");
  });

  it.each(["@sentry/replay", "@sentry/replay-canvas", "@sentry/feedback"])(
    "leaves Sentry's unused %s out of every bundle",
    (name) => {
      expect(resolve(name, { platform: "ios" })).toEqual(EMPTY);
      expect(resolve(name, { platform: "android", dev: true })).toEqual(EMPTY);
    },
  );

  it("leaves out the @sentry/browser modules that build the feedback widget on load", () => {
    const from = "/app/node_modules/@sentry/browser/build/npm/esm/prod/index.js";
    expect(resolve("./feedbackSync.js", { from })).toEqual(EMPTY);
    expect(resolve("./feedbackAsync.js", { from })).toEqual(EMPTY);
  });

  it.each(["@sentry/core", "@sentry/react-native", "@sentry/browser"])(
    "resolves %s as before",
    (name) => {
      expect(resolve(name)).toEqual({ type: "sourceFile", filePath: name });
    },
  );
});
