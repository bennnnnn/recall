import type { ConfigContext, ExpoConfig } from "expo/config";

import appJson from "./app.json";

function iosUrlSchemeFromClientId(iosClientId: string): string | null {
  const trimmed = iosClientId.trim();
  if (!trimmed.endsWith(".apps.googleusercontent.com")) return null;
  return `com.googleusercontent.apps.${trimmed.replace(".apps.googleusercontent.com", "")}`;
}

export default ({ config }: ConfigContext): ExpoConfig => {
  const base = appJson.expo as ExpoConfig;
  const plugins: ExpoConfig["plugins"] = [
    "expo-dev-client",
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

  return {
    ...config,
    ...base,
    plugins,
    extra: {
      ...base.extra,
      eas: {
        projectId: process.env.EXPO_PUBLIC_EAS_PROJECT_ID,
      },
    },
  };
};
