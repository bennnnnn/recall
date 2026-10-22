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

type CustomerInfo = { entitlements: { active: Record<string, { productIdentifier: string }> } };

const PLUS: CustomerInfo = { entitlements: { active: { plus: { productIdentifier: "plus_monthly:monthly" } } } };
const PRO: CustomerInfo = { entitlements: { active: { pro: { productIdentifier: "pro_monthly:monthly" } } } };
const PRO_PACKAGE = {
  identifier: "pro_monthly",
  presentedOfferingContext: { offeringIdentifier: "default", placementIdentifier: null, targetingContext: null },
  product: { identifier: "pro_monthly:monthly", priceString: "$9.99" },
};

/** What the native store answers each method with; any other method returns nothing. */
const NATIVE_ANSWERS: Record<string, unknown> = {
  isConfigured: true,
  logIn: { customerInfo: PLUS, created: false },
  getOfferings: { all: {}, current: { availablePackages: [PRO_PACKAGE], monthly: null } },
  getCustomerInfo: PLUS,
  purchasePackage: { productIdentifier: "pro_monthly", customerInfo: PRO },
  restorePurchases: PLUS,
  logOut: { entitlements: { active: {} } },
};

/** Every call into RNPurchases, the native module. */
const mockNativeCalls: { method: string; args: unknown[] }[] = [];
const mockNativePurchases = new Proxy(
  {},
  {
    get: (_module, method) =>
      typeof method !== "string" || method === "then"
        ? undefined
        : (...args: unknown[]) => {
            mockNativeCalls.push({ method, args });
            return method in NATIVE_ANSWERS ? Promise.resolve(NATIVE_ANSWERS[method]) : undefined;
          },
  },
);
/** The native module's events, by name. */
const mockNativeEvents = new Map<string, (event: unknown) => void>();
/** Every read of the web SDK, which a native production bundle leaves empty. */
const mockWebSdkReads: string[] = [];
const mockPlatform = { OS: "ios" };

const nativeCalls = (method: string) =>
  mockNativeCalls.filter((call) => call.method === method).map((call) => call.args);

describe("react-native-purchases in a native production bundle (no web SDK)", () => {
  beforeEach(() => {
    jest.resetModules();
    mockNativeCalls.length = 0;
    mockNativeEvents.clear();
    mockWebSdkReads.length = 0;
    mockPlatform.OS = "ios";
    (globalThis as { __DEV__?: boolean }).__DEV__ = false;
    process.env.EXPO_PUBLIC_REVENUECAT_IOS_API_KEY = "ios_key";
    process.env.EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY = "android_key";
    // The web SDK as a native production bundle has it: nothing may read from it.
    jest.doMock(
      "@revenuecat/purchases-js-hybrid-mappings",
      () =>
        new Proxy(
          {},
          {
            get: (_module, name) => {
              mockWebSdkReads.push(String(name));
              throw new Error(`The web SDK was used: ${String(name)}`);
            },
          },
        ),
    );
    jest.doMock("react-native", () => ({
      NativeModules: { RNPurchases: mockNativePurchases },
      NativeEventEmitter: class {
        addListener(name: string, listener: (event: unknown) => void) {
          mockNativeEvents.set(name, listener);
          return { remove: () => undefined };
        }
      },
      Platform: {
        get OS() {
          return mockPlatform.OS;
        },
        select: (options: Record<string, unknown>) => options[mockPlatform.OS] ?? options.default,
      },
    }));
    jest.doMock("@/lib/expoRuntime", () => ({ isExpoGo: () => false }));
  });

  it("loads and configures on the native store", () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- loaded after the mocks above
    const { default: Purchases } = require("react-native-purchases") as typeof import("react-native-purchases");
    Purchases.configure({ apiKey: "appl_key", appUserID: "user-1" });
    expect(nativeCalls("setupPurchases").map((args) => args.slice(0, 2))).toEqual([["appl_key", "user-1"]]);
    expect(mockWebSdkReads).toEqual([]);
  });

  it.each(["ios", "android"])("serves every call lib/purchases.ts makes from the native store on %s", async (os) => {
    mockPlatform.OS = os;
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- loaded after the mocks above
    const purchases = require("@/lib/purchases") as typeof import("@/lib/purchases");
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- the same module lib/purchases.ts loads
    const { default: Purchases } = require("react-native-purchases") as typeof import("react-native-purchases");

    await purchases.configurePurchases("user-1");
    await purchases.configurePurchases("user-2");
    const { pro } = (await purchases.getPlanPackages()).packages;
    expect(pro).toMatchObject({ plan: "pro", priceString: "$9.99", productId: "pro_monthly:monthly" });
    await expect(purchases.purchasePlanPackage(pro!)).resolves.toBe("pro");
    await expect(purchases.restorePurchases()).resolves.toBe("plus");

    const plans: string[] = [];
    const stop = await purchases.registerPlanChangeListener((plan) => plans.push(plan));
    mockNativeEvents.get("Purchases-CustomerInfoUpdated")?.(PRO);
    stop?.();
    mockNativeEvents.get("Purchases-CustomerInfoUpdated")?.(PLUS);
    expect(plans).toEqual(["pro"]);
    await purchases.signOutRevenueCat();

    expect(nativeCalls("setLogLevel")).toEqual([["WARN"]]);
    expect(nativeCalls("setupPurchases").map((args) => args.slice(0, 2))).toEqual([[`${os}_key`, "user-1"]]);
    expect(nativeCalls("logIn")).toEqual([["user-2"]]);
    expect(nativeCalls("getOfferings")).toEqual([[]]);
    // Android: Pro replaces the Plus subscription, prorated.
    expect(typeof Purchases.PRORATION_MODE.IMMEDIATE_WITH_TIME_PRORATION).toBe("number");
    const change =
      os === "android"
        ? { oldProductIdentifier: "plus_monthly", prorationMode: Purchases.PRORATION_MODE.IMMEDIATE_WITH_TIME_PRORATION }
        : null;
    expect(nativeCalls("getCustomerInfo")).toEqual(os === "android" ? [[]] : []);
    expect(nativeCalls("purchasePackage")).toEqual([
      ["pro_monthly", PRO_PACKAGE.presentedOfferingContext, change, null, null],
    ]);
    expect(nativeCalls("restorePurchases")).toEqual([[]]);
    expect(nativeCalls("logOut")).toEqual([[]]);
    expect(mockWebSdkReads).toEqual([]);
  });
});
