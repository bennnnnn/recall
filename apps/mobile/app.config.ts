import type { ConfigContext, ExpoConfig } from "expo/config";

import appJson from "./app.json";

function includeDevClientPlugin(buildProfile: string): boolean {
  return !buildProfile || buildProfile === "development";
}

function requirePublicApiUrlForReleaseBuild(
  buildProfile: string,
  apiUrl: string | undefined,
): void {
  if (buildProfile !== "production" && buildProfile !== "preview") return;
  if (apiUrl?.trim()) return;
  throw new Error(
    "EXPO_PUBLIC_API_URL must be set in EAS secrets for production and preview builds",
  );
}

function iosUrlSchemeFromClientId(iosClientId: string): string | null {
  const trimmed = iosClientId.trim();
  if (!trimmed.endsWith(".apps.googleusercontent.com")) return null;
  return `com.googleusercontent.apps.${trimmed.replace(".apps.googleusercontent.com", "")}`;
}

export default ({ config }: ConfigContext): ExpoConfig => {
  const base = appJson.expo as ExpoConfig;
  const buildProfile = process.env.EAS_BUILD_PROFILE ?? "";
  requirePublicApiUrlForReleaseBuild(buildProfile, process.env.EXPO_PUBLIC_API_URL);
  const includeDevClient = includeDevClientPlugin(buildProfile);
  const sentryDsn = process.env.EXPO_PUBLIC_SENTRY_DSN?.trim();
  const plugins: ExpoConfig["plugins"] = [
    ...(includeDevClient ? (["expo-dev-client"] as const) : []),
    ...(sentryDsn ? (["@sentry/react-native/expo"] as const) : []),
    ...(base.plugins ?? []),
  ];
  const iosUrlScheme = iosUrlSchemeFromClientId(
    process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID ?? "",
  );
  const webClientId = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID ?? "";

  if (webClientId && !/your-google/i.test(webClientId)) {
    const googlePluginConfig: { iosUrlScheme?: string } = {};
    if (iosUrlScheme) googlePluginConfig.iosUrlScheme = iosUrlScheme;
    plugins.push(["@react-native-google-signin/google-signin", googlePluginConfig]);
    if (iosUrlScheme) plugins.push("./plugins/googleSignInPodfile.js");
  }

  const iosInfoPlist: Record<string, unknown> = {
    ...(base.ios?.infoPlist ?? {}),
  };
  if (includeDevClient) {
    iosInfoPlist.NSAppTransportSecurity = { NSAllowsLocalNetworking: true };
  }

  return {
    ...config,
    ...base,
    plugins,
    ios: {
      ...base.ios,
      infoPlist: iosInfoPlist,
    },
    extra: {
      ...base.extra,
      eas: {
        projectId: process.env.EXPO_PUBLIC_EAS_PROJECT_ID,
      },
    },
  };
};
