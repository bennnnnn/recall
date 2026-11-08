const { withDangerousMod } = require("expo/config-plugins");
const fs = require("fs");
const path = require("path");

/**
 * react-native-purchases pins PurchasesHybridCommon to one version, and RevenueCat can publish
 * a release before CocoaPods trunk has it: 11.0.0 needs 20.1.0, which trunk never received
 * (its Nov 1-7 2026 freeze), so `pod install` failed on every fresh iOS build. The Podfile takes
 * that version's podspec from RevenueCat's own release tag; its dependency, RevenueCat itself,
 * still comes from trunk. The version is read from the installed package, so an upgrade moves
 * with it.
 */
function requiredVersion(projectRoot) {
  const podspec = path.join(
    path.dirname(require.resolve("react-native-purchases/package.json", { paths: [projectRoot] })),
    "RNPurchases.podspec",
  );
  const match = fs.readFileSync(podspec, "utf8").match(/dependency\s+"PurchasesHybridCommon",\s*'([^']+)'/);
  if (!match) throw new Error("purchasesHybridCommonPod: RNPurchases.podspec names no PurchasesHybridCommon version");
  return match[1];
}

/** The line it goes after, with its line ending: a Podfile saved on Windows ends in \r\n. */
const ANCHOR = / {2}use_expo_modules!(\r?\n)/;
/**
 * Any line this plugin (or a hand edit) left, one written for an older version included:
 * with either line ending, or none when it is the file's last line.
 */
const POD_LINE = /^[ \t]*pod ['"]PurchasesHybridCommon['"][^\r\n]*(?:\r?\n|$)/gm;

/**
 * The Podfile with exactly one PurchasesHybridCommon line, for `version`, after
 * `use_expo_modules!`. A prebuild without --clean keeps the Podfile it wrote before, so a line
 * for the last version is replaced, never kept: `pod install` would fail on the mismatch.
 */
function withPodLine(contents, version) {
  const spec = `https://raw.githubusercontent.com/RevenueCat/purchases-hybrid-common/${version}/PurchasesHybridCommon.podspec`;
  const rest = contents.replace(POD_LINE, "");
  if (!ANCHOR.test(rest)) {
    throw new Error(
      "purchasesHybridCommonPod: ios/Podfile has no `  use_expo_modules!` line to add PurchasesHybridCommon " +
        "after, so `pod install` would look for it on CocoaPods trunk, which lacks it. Expo's Podfile " +
        "template changed: update ANCHOR in plugins/purchasesHybridCommonPod.js.",
    );
  }
  return rest.replace(ANCHOR, (anchor, eol) => `${anchor}  pod 'PurchasesHybridCommon', :podspec => '${spec}'${eol}`);
}

function withPurchasesHybridCommonPod(config) {
  return withDangerousMod(config, [
    "ios",
    async (cfg) => {
      const podfilePath = path.join(cfg.modRequest.platformProjectRoot, "Podfile");
      const contents = await fs.promises.readFile(podfilePath, "utf8");
      const next = withPodLine(contents, requiredVersion(cfg.modRequest.projectRoot));
      if (next !== contents) await fs.promises.writeFile(podfilePath, next);
      return cfg;
    },
  ]);
}

module.exports = withPurchasesHybridCommonPod;
module.exports.withPodLine = withPodLine;
module.exports.requiredVersion = requiredVersion;
