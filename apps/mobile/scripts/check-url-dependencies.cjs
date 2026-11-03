// Exercise the real Expo dependency chain with Node's CommonJS loader.
const assert = require("node:assert/strict");
const { createRequire } = require("node:module");

// Expo Router 58 parses query strings with the platform's URLSearchParams. Before it, the router
// bundled query-string and decode-uri-component, which had two denial-of-service advisories
// (GHSA-vcc3-ghjq-m6fr, GHSA-qr28-fpjm-wq7f) and needed a pinned, patched copy. If either comes
// back into the router's tree, check its version against those advisories before shipping.
const fromRouter = createRequire(require.resolve("expo-router/package.json"));
for (const name of ["query-string", "decode-uri-component"]) {
  assert.throws(() => fromRouter.resolve(name), { code: "MODULE_NOT_FOUND" }, `${name} is back`);
}

const fromExpo = createRequire(require.resolve("expo/package.json"));
const fromMetro = createRequire(fromExpo.resolve("@expo/metro-config/package.json"));
const browserslist = fromMetro("browserslist");
assert.ok(browserslist(["last 1 chrome version"]).length > 0);
process.stdout.write("URL dependencies are compatible\n");
