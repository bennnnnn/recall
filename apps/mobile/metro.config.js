const { getDefaultConfig } = require('expo/metro-config');

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname);

const dedupedModules = new Set(["react-native-svg"]);

config.resolver.resolveRequest = (context, moduleName, platform) => {
  const root = moduleName.split("/")[0];
  if (dedupedModules.has(root)) {
    return {
      type: "sourceFile",
      filePath: require.resolve(moduleName),
    };
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
