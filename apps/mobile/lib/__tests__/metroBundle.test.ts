/**
 * What metro.config.js adds to the bundle and what it leaves out. The
 * RevenueCat rule leans on how react-native-purchases loads its web SDK, so the
 * real package is loaded here the way a native production bundle has it.
 */
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

  it("leaves RevenueCat's web SDK out of native production bundles only", () => {
    const sdk = "@revenuecat/purchases-js-hybrid-mappings";
    expect(resolve(sdk, { platform: "ios" })).toEqual(EMPTY);
    expect(resolve(sdk, { platform: "android" })).toEqual(EMPTY);
    // Development bundles (Expo Go, dev builds) and the web keep it.
    expect(resolve(sdk, { platform: "ios", dev: true })).toEqual({ type: "sourceFile", filePath: sdk });
    expect(resolve(sdk, { platform: "web" })).toEqual({ type: "sourceFile", filePath: sdk });
  });

  it.each([
    "@sentry/core",
    "@sentry/react-native",
    "@sentry/browser",
    "react-native-purchases",
    "@revenuecat/purchases-typescript-internal",
  ])(
    "resolves %s as before",
    (name) => {
      expect(resolve(name)).toEqual({ type: "sourceFile", filePath: name });
    },
  );
});

const mockNativePurchases = {
  setupPurchases: jest.fn(),
  setLogHandler: jest.fn(),
  addListener: jest.fn(),
  removeListeners: jest.fn(),
};

describe("react-native-purchases in a native production bundle (no web SDK)", () => {
  beforeEach(() => {
    jest.resetModules();
    // The web SDK as a native production bundle has it.
    jest.doMock("@revenuecat/purchases-js-hybrid-mappings", () => ({}));
    jest.doMock("react-native", () => ({
      NativeModules: { RNPurchases: mockNativePurchases },
      NativeEventEmitter: class {
        addListener() {
          return { remove: () => undefined };
        }
      },
      Platform: { OS: "ios", select: (options: { ios?: unknown }) => options.ios },
    }));
  });

  it("loads and configures on the native store", () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- loaded after the mocks above
    const { default: Purchases } = require("react-native-purchases") as typeof import("react-native-purchases");
    Purchases.configure({ apiKey: "appl_key", appUserID: "user-1" });
    expect(mockNativePurchases.setupPurchases).toHaveBeenCalledTimes(1);
    expect(mockNativePurchases.setupPurchases.mock.calls[0].slice(0, 2)).toEqual(["appl_key", "user-1"]);
  });
});
