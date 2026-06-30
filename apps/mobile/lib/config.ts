import Constants from "expo-constants";

export const config = {
  apiUrl: process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000",
  googleWebClientId:
    process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID ??
    "your-google-web-client-id.apps.googleusercontent.com",
  googleIosClientId:
    process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID ??
    "your-ios-client-id.apps.googleusercontent.com",
  devAuthEnabled: process.env.EXPO_PUBLIC_DEV_AUTH_ENABLED === "true",
  appName: "Recall",
  isDev: __DEV__,
} as const;

/** True when real Google OAuth client IDs are set (not placeholders). */
export function isGoogleSignInConfigured(): boolean {
  const placeholder = /your-(google|ios)/i;
  return (
    !placeholder.test(config.googleWebClientId) &&
    !placeholder.test(config.googleIosClientId)
  );
}

export function getApiUrl(): string {
  // .env wins over app.json (app.json extra is fallback for EAS builds)
  if (process.env.EXPO_PUBLIC_API_URL) {
    return process.env.EXPO_PUBLIC_API_URL;
  }
  const extra = Constants.expoConfig?.extra as { apiUrl?: string } | undefined;
  return extra?.apiUrl ?? "http://localhost:8000";
}
