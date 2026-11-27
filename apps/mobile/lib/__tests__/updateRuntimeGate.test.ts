/**
 * The over-the-air update gate (scripts/check-update-runtime.cjs, run by
 * mobile-update.yml): an update goes out only with the native fingerprint of the
 * channel's newest build, and the release config's runtime policy is that fingerprint.
 */
declare const __dirname: string;

const { join } = jest.requireActual<{ join(...parts: string[]): string }>("node:path");
// eslint-disable-next-line @typescript-eslint/no-require-imports -- the CommonJS script the workflow runs
const { runtimeMismatch } = require(join(__dirname, "..", "..", "scripts", "check-update-runtime.cjs")) as {
  runtimeMismatch(
    platform: string,
    channel: string,
    update: string | null,
    build: { id: string; runtimeVersion: string | null } | null,
  ): string | null;
};

describe("the update gate", () => {
  it("lets an update out with the newest build's fingerprint", () => {
    expect(runtimeMismatch("ios", "production", "abc", { id: "b1", runtimeVersion: "abc" })).toBeNull();
  });

  it("stops an update whose native code differs from the newest build", () => {
    const problem = runtimeMismatch("android", "production", "new", { id: "b1", runtimeVersion: "old" });
    expect(problem).toContain("android");
    expect(problem).toContain("Ship a store build");
    expect(problem).toContain("eas fingerprint:compare --build-id b1");
  });

  it("stops an update when the channel has no build, or its fingerprint is unknown", () => {
    expect(runtimeMismatch("ios", "preview", "abc", null)).toContain('no finished build listens on the "preview"');
    expect(runtimeMismatch("ios", "preview", null, { id: "b1", runtimeVersion: "abc" })).toContain(
      "could not work out",
    );
    expect(runtimeMismatch("ios", "preview", "abc", { id: "b1", runtimeVersion: null })).not.toBeNull();
  });

  it("is what decides which builds take an update: the fingerprint policy", () => {
    const appJson = jest.requireActual<{ expo: { runtimeVersion: unknown } }>(join(__dirname, "..", "..", "app.json"));
    expect(appJson.expo.runtimeVersion).toEqual({ policy: "fingerprint" });
  });
});
