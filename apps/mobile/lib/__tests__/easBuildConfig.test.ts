import {
  includeDevClientPlugin,
  requirePublicApiUrlForReleaseBuild,
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
});
