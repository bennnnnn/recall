import { isConsentCancelled, readServerAuthCode } from "@/lib/google-integration-auth-code";

const mockConfigure = jest.fn();
const mockHasPlayServices = jest.fn();
const mockGetCurrentUser = jest.fn();
const mockAddScopes = jest.fn();
const mockSignIn = jest.fn();
const mockSignInSilently = jest.fn();

jest.mock("@/lib/config", () => ({
  config: {
    googleWebClientId: "web-client",
    googleIosClientId: "ios-client",
  },
}));

jest.mock("@react-native-google-signin/google-signin", () => ({
  GoogleSignin: {
    configure: (...args: unknown[]) => mockConfigure(...args),
    hasPlayServices: (...args: unknown[]) => mockHasPlayServices(...args),
    getCurrentUser: () => mockGetCurrentUser(),
    addScopes: (...args: unknown[]) => mockAddScopes(...args),
    signIn: () => mockSignIn(),
    signInSilently: () => mockSignInSilently(),
  },
  statusCodes: { SIGN_IN_CANCELLED: "SIGN_IN_CANCELLED" },
}));

import { requestGoogleIntegrationAuthCode } from "@/lib/google-integration-auth";

describe("readServerAuthCode", () => {
  it("returns trimmed code when present", () => {
    expect(readServerAuthCode({ data: { serverAuthCode: "abc123" } })).toBe("abc123");
  });

  it("returns null for empty or missing code", () => {
    expect(readServerAuthCode(null)).toBeNull();
    expect(readServerAuthCode({ data: { serverAuthCode: "  " } })).toBeNull();
    expect(readServerAuthCode({ data: {} })).toBeNull();
  });

  it("does not read a leftover top-level serverAuthCode from getCurrentUser()", () => {
    expect(readServerAuthCode({ serverAuthCode: "stale-from-signin" } as never)).toBeNull();
  });
});

describe("isConsentCancelled", () => {
  it("detects cancelled consent responses", () => {
    expect(isConsentCancelled({ type: "cancelled" })).toBe(true);
    expect(isConsentCancelled({ type: "success" })).toBe(false);
    expect(isConsentCancelled(null)).toBe(false);
  });
});

describe("requestGoogleIntegrationAuthCode", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockHasPlayServices.mockResolvedValue(true);
    mockGetCurrentUser.mockReturnValue(null);
    mockAddScopes.mockResolvedValue(null);
    mockSignIn.mockResolvedValue({ data: { serverAuthCode: "fresh-code" } });
  });

  it("configures offline access and forceCodeForRefreshToken", async () => {
    await requestGoogleIntegrationAuthCode(["scope-a"]);
    expect(mockConfigure).toHaveBeenCalledWith(
      expect.objectContaining({
        offlineAccess: true,
        forceCodeForRefreshToken: true,
        scopes: ["scope-a"],
      }),
    );
  });

  it("uses addScopes code and does not fall back to getCurrentUser().serverAuthCode", async () => {
    mockGetCurrentUser.mockReturnValue({ serverAuthCode: "stale-from-signin" });
    mockAddScopes.mockResolvedValue({ data: { serverAuthCode: "from-add-scopes" } });

    const code = await requestGoogleIntegrationAuthCode(["scope-a"]);

    expect(code).toBe("from-add-scopes");
    expect(mockSignIn).not.toHaveBeenCalled();
    expect(mockSignInSilently).not.toHaveBeenCalled();
  });

  it("signs in for a new code instead of reusing the cached user code", async () => {
    mockGetCurrentUser.mockReturnValue({ serverAuthCode: "stale-from-signin" });
    mockAddScopes.mockResolvedValue({ data: { serverAuthCode: null } });
    mockSignIn.mockResolvedValue({ data: { serverAuthCode: "from-sign-in" } });

    const code = await requestGoogleIntegrationAuthCode(["scope-a"]);

    expect(code).toBe("from-sign-in");
    expect(mockSignIn).toHaveBeenCalled();
    expect(mockSignInSilently).not.toHaveBeenCalled();
  });

  it("treats a cancelled addScopes response as cancel, not a missing code", async () => {
    mockGetCurrentUser.mockReturnValue({ serverAuthCode: "stale" });
    mockAddScopes.mockResolvedValue({ type: "cancelled", data: null });

    await expect(requestGoogleIntegrationAuthCode(["scope-a"])).rejects.toThrow(
      "Connect cancelled",
    );
    expect(mockSignIn).not.toHaveBeenCalled();
  });
});
