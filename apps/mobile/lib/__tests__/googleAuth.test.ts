/**
 * Backing out of Google's account picker said "Sign-in failed": google-signin answers a
 * cancel with `{ type: "cancelled", data: null }`, which was read as a reply with no token.
 */
import { formatGoogleSignInError, signInWithGoogleIdToken } from "@/lib/google-auth";

jest.mock("react-native", () => ({ Platform: { OS: "android" } }));
jest.mock("@/lib/expoRuntime", () => ({ isExpoGo: () => false }));
jest.mock("@/lib/config", () => ({
  config: { googleWebClientId: "web-client", googleIosClientId: "ios-client" },
  isGoogleSignInConfigured: () => true,
  isGoogleWebClientConfigured: () => true,
}));

const mockSignIn = jest.fn();
jest.mock("@react-native-google-signin/google-signin", () => ({
  GoogleSignin: {
    configure: jest.fn(),
    hasPlayServices: jest.fn(async () => true),
    signIn: () => mockSignIn(),
  },
  statusCodes: { IN_PROGRESS: "IN_PROGRESS", PLAY_SERVICES_NOT_AVAILABLE: "PLAY_SERVICES_NOT_AVAILABLE" },
}));

/** What the login screen does with a failed sign-in: a cancel says nothing. */
async function loginScreenKey(): Promise<string> {
  try {
    await signInWithGoogleIdToken();
    return "signed-in";
  } catch (error) {
    return formatGoogleSignInError(error);
  }
}

it("hands back the account's ID token", async () => {
  mockSignIn.mockResolvedValueOnce({ type: "success", data: { idToken: "google.id.token" } });
  await expect(signInWithGoogleIdToken()).resolves.toBe("google.id.token");
});

it("reads backing out of the account picker as a cancel, never a failure", async () => {
  mockSignIn.mockResolvedValueOnce({ type: "cancelled", data: null });
  await expect(loginScreenKey()).resolves.toBe("cancelled");
});

it("still fails a sign-in that brings no token", async () => {
  mockSignIn.mockResolvedValueOnce({ type: "success", data: { idToken: null } });
  await expect(loginScreenKey()).resolves.toBe("generic");
});

it("words a phone without Play services as such", async () => {
  mockSignIn.mockRejectedValueOnce(Object.assign(new Error("unavailable"), { code: "PLAY_SERVICES_NOT_AVAILABLE" }));
  await expect(loginScreenKey()).resolves.toBe("play_services_missing");
});
