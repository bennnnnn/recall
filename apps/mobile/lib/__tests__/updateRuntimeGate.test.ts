/**
 * The over-the-air update gate (scripts/check-update-runtime.cjs, run by
 * mobile-update.yml): an update goes out only with the native fingerprint of the
 * channel's newest build on each platform that has one, and the release config's
 * runtime policy is that fingerprint.
 */
declare const __dirname: string;

type Build = { id: string; runtimeVersion: string | null } | null;
type Platform = { platform: string; update: string | null; build: Build };

const { join } = jest.requireActual<{ join(...parts: string[]): string }>("node:path");
// eslint-disable-next-line @typescript-eslint/no-require-imports -- the CommonJS script the workflow runs
const { gateUpdate } = require(join(__dirname, "..", "..", "scripts", "check-update-runtime.cjs")) as {
  gateUpdate(channel: string, platforms: Platform[]): { notes: string[]; problems: string[] };
};

const ios = (update: string | null, build: Build): Platform => ({ platform: "ios", update, build });
const android = (update: string | null, build: Build): Platform => ({ platform: "android", update, build });

describe("the update gate", () => {
  it("lets an update out with each platform's newest build fingerprint", () => {
    const { notes, problems } = gateUpdate("production", [
      ios("abc", { id: "b1", runtimeVersion: "abc" }),
      android("def", { id: "b2", runtimeVersion: "def" }),
    ]);
    expect(problems).toEqual([]);
    expect(notes).toHaveLength(2);
  });

  it("stops an update whose native code differs from a platform's newest build", () => {
    const { problems } = gateUpdate("production", [
      ios("abc", { id: "b1", runtimeVersion: "abc" }),
      android("new", { id: "b2", runtimeVersion: "old" }),
    ]);
    expect(problems).toHaveLength(1);
    expect(problems[0]).toContain("android");
    expect(problems[0]).toContain("Ship a store build");
    expect(problems[0]).toContain("eas fingerprint:compare --build-id b2");
  });

  it("skips a platform the channel has no build for, saying so, and still checks the other", () => {
    const passes = gateUpdate("preview", [ios("abc", { id: "b1", runtimeVersion: "abc" }), android("def", null)]);
    expect(passes.problems).toEqual([]);
    expect(passes.notes).toContainEqual(expect.stringContaining('android: skipped, no finished build listens on the "preview"'));

    const fails = gateUpdate("preview", [ios("new", { id: "b1", runtimeVersion: "old" }), android("def", null)]);
    expect(fails.problems).toHaveLength(1);
    expect(fails.problems[0]).toContain("ios");
  });

  it("stops an update when no platform has a build, or a fingerprint is unknown", () => {
    expect(gateUpdate("preview", [ios("abc", null), android("def", null)]).problems).toEqual([
      expect.stringContaining('No finished build listens on the "preview" channel on any platform'),
    ]);
    expect(gateUpdate("preview", [ios(null, { id: "b1", runtimeVersion: "abc" })]).problems).toEqual([
      expect.stringContaining("could not work out"),
    ]);
    expect(gateUpdate("preview", [ios("abc", { id: "b1", runtimeVersion: null })]).problems).toHaveLength(1);
  });

  it("is what decides which builds take an update: the fingerprint policy", () => {
    const appJson = jest.requireActual<{ expo: { runtimeVersion: unknown } }>(join(__dirname, "..", "..", "app.json"));
    expect(appJson.expo.runtimeVersion).toEqual({ policy: "fingerprint" });
  });
});
