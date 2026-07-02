import type { ConfigContext, ExpoConfig } from "expo/config";

import appJson from "./app.json";
import {
  includeDevClientPlugin,
  requirePublicApiUrlForReleaseBuild,
} from "./lib/easBuildConfig";

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
  const plugins: ExpoConfig["plugins"] = [
    ...(includeDevClient ? (["expo-dev-client"] as const) : []),
    ...(base.plugins ?? []),
  ];
  const iosUrlScheme = iosUrlSchemeFromClientId(
    process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID ?? "",
  );

  if (iosUrlScheme) {
    plugins.push([
      "@react-native-google-signin/google-signin",
      { iosUrlScheme },
    ]);
    plugins.push("./plugins/googleSignInPodfile.js");
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
