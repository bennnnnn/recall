import Constants from "expo-constants";

import { shouldShowAppleSignInButton } from "@/lib/apple-auth";

jest.mock("expo-constants", () => ({
  __esModule: true,
  default: { expoConfig: { extra: {} } },
}));

jest.mock("react-native", () => ({
  Platform: { OS: "ios" },
}));

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
