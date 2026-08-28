/** EAS build profile helpers. CJS so Expo's isolated app.config compile can require it. */

const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "::1"]);

function includeDevClientPlugin(buildProfile) {
  return !buildProfile || buildProfile === "development";
}

function assertReleaseApiUrl(apiUrl, envName) {
  const trimmed = apiUrl?.trim();
  if (!trimmed) {
    throw new Error(`${envName} must be set to a public https:// URL`);
  }
  let parsed;
  try {
    parsed = new URL(trimmed);
  } catch {
    throw new Error(`${envName} must be a valid https:// URL, got "${trimmed}"`);
  }
  const host = parsed.hostname.toLowerCase();
  if (parsed.protocol !== "https:" || LOOPBACK_HOSTS.has(host)) {
    throw new Error(
      `${envName} must be a public https:// URL for release builds, got "${trimmed}"`,
    );
  }
}

function requirePublicApiUrlForReleaseBuild(buildProfile, apiUrl) {
  if (buildProfile !== "production" && buildProfile !== "preview") return;
  try {
    assertReleaseApiUrl(apiUrl, "EXPO_PUBLIC_API_URL");
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(
      `${message}. Set EXPO_PUBLIC_API_URL in EAS secrets for production and preview builds`,
    );
  }
}

function requireReleaseBuildSecrets(buildProfile, buildPlatform, env) {
  if (buildProfile !== "production" && buildProfile !== "preview") return;

  requirePublicApiUrlForReleaseBuild(buildProfile, env.EXPO_PUBLIC_API_URL);
  const required = [
    ["EXPO_PUBLIC_EAS_PROJECT_ID", env.EXPO_PUBLIC_EAS_PROJECT_ID],
    ["EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID", env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID],
  ];
  if (buildPlatform !== "android") {
    required.push(
      ["EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID", env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID],
      ["EXPO_PUBLIC_REVENUECAT_IOS_API_KEY", env.EXPO_PUBLIC_REVENUECAT_IOS_API_KEY],
    );
  }
  if (buildPlatform !== "ios") {
    required.push([
      "EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY",
      env.EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY,
    ]);
  }

  const missing = required.filter(([, value]) => !value?.trim()).map(([key]) => key);
  if (missing.length > 0) {
    throw new Error(
      `Missing EAS secrets for ${buildProfile} ${buildPlatform || "release"} build: ${missing.join(", ")}`,
    );
  }
}

module.exports = {
  includeDevClientPlugin,
  assertReleaseApiUrl,
  requirePublicApiUrlForReleaseBuild,
  requireReleaseBuildSecrets,
};
