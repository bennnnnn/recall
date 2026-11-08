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

function withPurchasesHybridCommonPod(config) {
  return withDangerousMod(config, [
    "ios",
    async (cfg) => {
      const podfilePath = path.join(cfg.modRequest.platformProjectRoot, "Podfile");
      let contents = await fs.promises.readFile(podfilePath, "utf8");
      if (!contents.includes("pod 'PurchasesHybridCommon'")) {
        const version = requiredVersion(cfg.modRequest.projectRoot);
        const spec = `https://raw.githubusercontent.com/RevenueCat/purchases-hybrid-common/${version}/PurchasesHybridCommon.podspec`;
        contents = contents.replace(
          "  use_expo_modules!\n",
          `  use_expo_modules!\n  pod 'PurchasesHybridCommon', :podspec => '${spec}'\n`,
        );
        await fs.promises.writeFile(podfilePath, contents);
      }
      return cfg;
    },
  ]);
}

module.exports = withPurchasesHybridCommonPod;
