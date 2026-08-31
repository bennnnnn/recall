const fs = require("fs");
const path = require("path");
const { getDefaultConfig } = require("expo/metro-config");

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname);

/**
 * Pin react-native-svg to a single physical copy (pnpm can otherwise hand
 * Metro two and Android double-registers RNSVGCircle). Resolve via Metro so
 * the package.json "react-native" field (`src/`) is used — Node's
 * require.resolve picks lib/commonjs and skips Fabric codegen.
 */
const dedupedModules = new Set(["react-native-svg"]);
const appPackageJson = path.join(__dirname, "package.json");
const webrtcInstalled = fs.existsSync(path.join(__dirname, "node_modules/react-native-webrtc"));
const webrtcStub = path.join(__dirname, "lib/webrtcStub.js");

config.resolver.resolveRequest = (context, moduleName, platform) => {
  const root = moduleName.split("/")[0];
  if (dedupedModules.has(root)) {
    return context.resolveRequest(
      { ...context, originModulePath: appPackageJson },
      moduleName,
      platform,
    );
  }
  // Metro still extracts require("react-native-webrtc") from realtimeVoice.ts
  // at bundle time. Without a fallback, a missing install red-screens the
  // whole chat screen — not just Live Talk.
  if (moduleName === "react-native-webrtc" && !webrtcInstalled) {
    return { type: "sourceFile", filePath: webrtcStub };
  }
  return context.resolveRequest(context, moduleName, platform);
};

// Keep Jest-only tooling out of the app bundle (SDK 52+ handles monorepo resolution;
// avoid extraNodeModules — it can break RN global init with "property is not writable").
config.resolver.blockList = [
  ...(Array.isArray(config.resolver.blockList) ? config.resolver.blockList : []),
  /\/node_modules\/jest\//,
  /\/node_modules\/ts-jest\//,
  /\/lib\/__tests__\//,
];

// Bind IPv4 so iOS Simulator (127.0.0.1) can reach Metro when ::1-only would fail.
config.server = {
  ...(config.server ?? {}),
  host: "0.0.0.0",
};

module.exports = config;
