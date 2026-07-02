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
