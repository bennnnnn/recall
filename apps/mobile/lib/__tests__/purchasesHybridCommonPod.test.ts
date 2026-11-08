/**
 * plugins/purchasesHybridCommonPod.js: the iOS Podfile takes PurchasesHybridCommon's podspec
 * from RevenueCat's release tag, at the version the installed RNPurchases.podspec needs.
 */
import * as ts from "typescript";

declare const __dirname: string;

/** Node's own modules, as far as this test uses them: the test types leave out @types/node. */
// eslint-disable-next-line @typescript-eslint/no-require-imports -- see above
const { mkdtempSync, rmSync } = require("fs") as {
  mkdtempSync: (prefix: string) => string;
  rmSync: (dir: string, options: { recursive: true; force: true }) => void;
};
// eslint-disable-next-line @typescript-eslint/no-require-imports -- see above
const { tmpdir } = require("os") as { tmpdir: () => string };

type DangerousMod = (cfg: { modRequest: { platformProjectRoot: string; projectRoot: string } }) => Promise<unknown>;

// The mod itself, so a test can run it on a Podfile of its own.
jest.mock("expo/config-plugins", () => ({
  withDangerousMod: (config: object, [, mod]: [string, DangerousMod]) => ({ ...config, mod }),
}));

type Plugin = ((config: object) => { mod: DangerousMod }) & {
  withPodLine: (contents: string, version: string) => string;
  requiredVersion: (projectRoot: string) => string;
};
// eslint-disable-next-line @typescript-eslint/no-require-imports -- the config plugin is CommonJS
const plugin: Plugin = require("../../plugins/purchasesHybridCommonPod.js");

const PROJECT_ROOT = ts.sys.resolvePath(`${__dirname}/../..`);
const spec = (version: string) =>
  `https://raw.githubusercontent.com/RevenueCat/purchases-hybrid-common/${version}/PurchasesHybridCommon.podspec`;
const line = (version: string) => `  pod 'PurchasesHybridCommon', :podspec => '${spec(version)}'\n`;

/** Expo's Podfile, cut to the lines around the anchor. */
const PODFILE = [
  "target 'Recall' do\n",
  "  use_expo_modules!\n",
  "\n",
  "  config = use_native_modules!(config_command)\n",
  "end\n",
].join("");

describe("withPodLine", () => {
  it("adds the line after use_expo_modules!", () => {
    expect(plugin.withPodLine(PODFILE, "20.1.0")).toBe(PODFILE.replace("  use_expo_modules!\n", `  use_expo_modules!\n${line("20.1.0")}`));
  });

  it("replaces a line an older prebuild left, so an upgrade never keeps the old podspec", () => {
    // `pnpm ios:sim` prebuilds without --clean: the Podfile keeps what the last one wrote.
    const stale = plugin.withPodLine(PODFILE, "20.1.0");
    const upgraded = plugin.withPodLine(stale, "20.2.0");
    expect(upgraded).toContain(line("20.2.0"));
    expect(upgraded).not.toContain("20.1.0");
    expect(upgraded.match(/pod 'PurchasesHybridCommon'/g)).toHaveLength(1);
    expect(upgraded).toBe(plugin.withPodLine(PODFILE, "20.2.0"));
  });

  it("is unchanged when run again at the same version", () => {
    const once = plugin.withPodLine(PODFILE, "20.1.0");
    expect(plugin.withPodLine(once, "20.1.0")).toBe(once);
  });

  it("fails the prebuild, by name, when the Podfile has no use_expo_modules! line", () => {
    const changed = PODFILE.replace("  use_expo_modules!\n", "  use_expo_modules!(exclude: [])\n");
    expect(() => plugin.withPodLine(changed, "20.1.0")).toThrow(/purchasesHybridCommonPod: .*use_expo_modules!/);
  });
});

describe("the iOS mod", () => {
  let iosDir: string;
  beforeEach(() => {
    iosDir = mkdtempSync(`${tmpdir()}/podfile-`);
  });
  afterEach(() => {
    rmSync(iosDir, { recursive: true, force: true });
  });

  const run = () => plugin({}).mod({ modRequest: { platformProjectRoot: iosDir, projectRoot: PROJECT_ROOT } });
  const podfile = () => ts.sys.readFile(`${iosDir}/Podfile`);

  it("writes the version the installed RNPurchases.podspec needs, over a stale one", async () => {
    const version = plugin.requiredVersion(PROJECT_ROOT);
    const podspec = ts.sys.readFile(`${PROJECT_ROOT}/node_modules/react-native-purchases/RNPurchases.podspec`);
    expect(podspec).toContain(`"PurchasesHybridCommon", '${version}'`);

    ts.sys.writeFile(`${iosDir}/Podfile`, plugin.withPodLine(PODFILE, "0.0.1"));
    await run();
    expect(podfile()).toBe(plugin.withPodLine(PODFILE, version));
  });

  it("rejects, and leaves the Podfile alone, when the anchor is missing", async () => {
    ts.sys.writeFile(`${iosDir}/Podfile`, "target 'Recall' do\nend\n");
    await expect(run()).rejects.toThrow(/purchasesHybridCommonPod: .*use_expo_modules!/);
    expect(podfile()).toBe("target 'Recall' do\nend\n");
  });
});
