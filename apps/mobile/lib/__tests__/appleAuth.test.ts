import Constants from "expo-constants";

import { shouldShowAppleSignInButton, signInWithAppleCredentials } from "@/lib/apple-auth";

jest.mock("expo-constants", () => ({
  __esModule: true,
  default: { expoConfig: { extra: {} } },
}));

jest.mock("react-native", () => ({
  Platform: { OS: "ios" },
}));

const mockSignInAsync = jest.fn();
jest.mock("expo-apple-authentication", () => ({
  isAvailableAsync: jest.fn(async () => true),
  signInAsync: (...args: unknown[]) => mockSignInAsync(...args),
  AppleAuthenticationScope: { FULL_NAME: 0, EMAIL: 1 },
}));

jest.mock("expo-crypto", () => ({
  CryptoDigestAlgorithm: { SHA256: "SHA-256" },
  getRandomBytes: jest.fn(() => new Uint8Array([0, 1, 254, 255])),
  digestStringAsync: jest.fn(async (_algorithm: string, value: string) => `sha256(${value})`),
}));

describe("signInWithAppleCredentials", () => {
  it("binds Apple's token to this sign-in with a hashed nonce and keeps the raw one", async () => {
    mockSignInAsync.mockResolvedValue({
      identityToken: "apple.id.token",
      fullName: { givenName: "Ada", familyName: "Lovelace" },
    });

    const result = await signInWithAppleCredentials();

    // Apple gets SHA-256(raw) and echoes it in the token; only the server,
    // which receives the raw value, can match the two.
    expect(mockSignInAsync).toHaveBeenCalledWith(
      expect.objectContaining({ nonce: "sha256(0001feff)" }),
    );
    expect(result).toEqual({
      idToken: "apple.id.token",
      name: "Ada Lovelace",
      nonce: "0001feff",
    });
  });
});

function setExtra(extra: Record<string, unknown>): void {
  (Constants as unknown as { expoConfig: { extra: Record<string, unknown> } }).expoConfig = {
    extra,
  };
}

describe("shouldShowAppleSignInButton", () => {
  it("shows the Apple button on iOS", () => {
    setExtra({ appleSignIn: true });
    expect(shouldShowAppleSignInButton()).toBe(true);
    setExtra({});
    expect(shouldShowAppleSignInButton()).toBe(true);
  });

  it("hides it in a simulator build that left Sign in with Apple out", () => {
    setExtra({ appleSignIn: false });
    expect(shouldShowAppleSignInButton()).toBe(false);
  });
});
