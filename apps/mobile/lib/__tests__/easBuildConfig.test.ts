import {
  includeDevClientPlugin,
  requirePublicApiUrlForReleaseBuild,
  requireReleaseBuildSecrets,
} from "@/lib/easBuildConfig";

describe("easBuildConfig", () => {
  it("includes dev client only for local/dev EAS profile", () => {
    expect(includeDevClientPlugin("")).toBe(true);
    expect(includeDevClientPlugin("development")).toBe(true);
    expect(includeDevClientPlugin("preview")).toBe(false);
    expect(includeDevClientPlugin("production")).toBe(false);
  });

  it("requires EXPO_PUBLIC_API_URL for release builds", () => {
    expect(() => requirePublicApiUrlForReleaseBuild("development", undefined)).not.toThrow();
    expect(() =>
      requirePublicApiUrlForReleaseBuild("production", "https://api.example.com"),
    ).not.toThrow();
    expect(() => requirePublicApiUrlForReleaseBuild("production", undefined)).toThrow(
      /EXPO_PUBLIC_API_URL/,
    );
    expect(() => requirePublicApiUrlForReleaseBuild("preview", "  ")).toThrow(
      /EXPO_PUBLIC_API_URL/,
    );
  });

  const completeEnv = {
    EXPO_PUBLIC_API_URL: "https://api.recall.test",
    EXPO_PUBLIC_EAS_PROJECT_ID: "project-id",
    EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID: "web.apps.googleusercontent.com",
    EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID: "ios.apps.googleusercontent.com",
    EXPO_PUBLIC_REVENUECAT_IOS_API_KEY: "appl_test",
    EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY: "goog_test",
  };

  it("requires beta-critical service keys for release builds", () => {
    expect(() =>
      requireReleaseBuildSecrets("production", "ios", completeEnv),
    ).not.toThrow();
    expect(() =>
      requireReleaseBuildSecrets("production", "ios", {
        ...completeEnv,
        EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID: "",
        EXPO_PUBLIC_REVENUECAT_IOS_API_KEY: undefined,
      }),
    ).toThrow(/EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID.*EXPO_PUBLIC_REVENUECAT_IOS_API_KEY/);
  });

  it("requires only platform-relevant RevenueCat keys", () => {
    expect(() =>
      requireReleaseBuildSecrets("preview", "android", {
        ...completeEnv,
        EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID: undefined,
        EXPO_PUBLIC_REVENUECAT_IOS_API_KEY: undefined,
      }),
    ).not.toThrow();
    expect(() =>
      requireReleaseBuildSecrets("preview", "android", {
        ...completeEnv,
        EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY: "",
      }),
    ).toThrow(/EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY/);
  });

  it("does not require release secrets for development builds", () => {
    expect(() => requireReleaseBuildSecrets("development", "ios", {})).not.toThrow();
  });
});
