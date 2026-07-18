// BUG FIX regression: LoginScreen used a single shared `busy` boolean for
// every sign-in button (Apple/Google/dev), so tapping ONE button made ALL
// visible buttons render their spinner simultaneously — reported live with a
// screenshot ("all buttons process instead of just the one that got
// pressed"). Native/config-heavy deps are stubbed so import-time stays safe,
// mirroring the mocking pattern established in components/__tests__.
import { act } from "react";
import { render, fireEvent } from "@testing-library/react-native";

import LoginScreen from "@/app/login";

jest.mock("@/lib/haptics", () => ({
  tap: jest.fn(),
  selection: jest.fn(),
  notifySuccess: jest.fn(),
  notifyWarning: jest.fn(),
}));
jest.mock("expo-router", () => ({
  Redirect: () => null,
}));
jest.mock("expo-linear-gradient", () => {
  const { View } = jest.requireActual("react-native");
  return { LinearGradient: View };
});
jest.mock("react-native-safe-area-context", () => {
  const { View } = jest.requireActual("react-native");
  return { SafeAreaView: View };
});
jest.mock("@expo/vector-icons", () => ({ Ionicons: "Ionicons" }));
jest.mock("@/lib/apple-auth", () => ({
  shouldShowAppleSignInButton: () => true,
  formatAppleSignInError: () => "generic",
}));
jest.mock("@/lib/google-auth", () => ({
  isExpoGo: () => false,
  formatGoogleSignInError: () => "generic",
}));
jest.mock("@/lib/config", () => ({
  config: { devAuthEnabled: false },
  isGoogleSignInConfigured: () => true,
  isGoogleWebClientConfigured: () => true,
}));
jest.mock("@/lib/legalUrls", () => ({
  getLegalPrivacyUrl: () => "https://example.com/privacy",
  getLegalTermsUrl: () => "https://example.com/terms",
}));

let resolveApple: (() => void) | undefined;
let resolveGoogle: (() => void) | undefined;

jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    token: null,
    loading: false,
    onboarded: true,
    signInWithApple: () =>
      new Promise<void>((resolve) => {
        resolveApple = resolve;
      }),
    signInWithGoogle: () =>
      new Promise<void>((resolve) => {
        resolveGoogle = resolve;
      }),
    signInWithDev: () => Promise.resolve(),
  }),
}));

describe("LoginScreen", () => {
  beforeEach(() => {
    resolveApple = undefined;
    resolveGoogle = undefined;
  });

  it("BUG FIX regression: only the tapped button shows its spinner, not every visible button", async () => {
    const { getByText, queryByText } = await render(<LoginScreen />);

    // Both buttons rendered with their normal (non-busy) content.
    expect(getByText("login.apple")).toBeOnTheScreen();
    expect(getByText("login.google")).toBeOnTheScreen();

    await act(async () => {
      fireEvent.press(getByText("login.apple"));
    });

    // The tapped (Apple) button's label is replaced by its spinner...
    expect(queryByText("login.apple")).toBeNull();
    // ...but the Google button, which was never pressed, must still show its
    // own label/icon, not a spinner too.
    expect(getByText("login.google")).toBeOnTheScreen();

    await act(async () => {
      resolveApple?.();
    });
  });

  it("restores the tapped button's label after sign-in resolves", async () => {
    const { getByText, queryByText } = await render(<LoginScreen />);

    await act(async () => {
      fireEvent.press(getByText("login.google"));
    });
    expect(queryByText("login.google")).toBeNull();

    await act(async () => {
      resolveGoogle?.();
    });
    expect(getByText("login.google")).toBeOnTheScreen();
  });
});
