/** EAS build profile helpers (pure — testable from app.config.ts). */

export function includeDevClientPlugin(buildProfile: string): boolean {
  return !buildProfile || buildProfile === "development";
}

export function requirePublicApiUrlForReleaseBuild(
  buildProfile: string,
  apiUrl: string | undefined,
): void {
  if (buildProfile !== "production" && buildProfile !== "preview") return;
  if (apiUrl?.trim()) return;
  throw new Error(
    "EXPO_PUBLIC_API_URL must be set in EAS secrets for production and preview builds",
  );
}

type ReleaseBuildEnvironment = {
  [key: string]: string | undefined;
  EXPO_PUBLIC_API_URL?: string;
  EXPO_PUBLIC_EAS_PROJECT_ID?: string;
  EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID?: string;
  EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID?: string;
  EXPO_PUBLIC_REVENUECAT_IOS_API_KEY?: string;
  EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY?: string;
};

export function requireReleaseBuildSecrets(
  buildProfile: string,
  buildPlatform: string,
  env: ReleaseBuildEnvironment,
): void {
  if (buildProfile !== "production" && buildProfile !== "preview") return;

  requirePublicApiUrlForReleaseBuild(buildProfile, env.EXPO_PUBLIC_API_URL);
  const required: Array<[keyof ReleaseBuildEnvironment, string | undefined]> = [
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
