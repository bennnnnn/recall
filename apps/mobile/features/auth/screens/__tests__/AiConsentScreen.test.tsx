import { act } from "react";
import { fireEvent, render } from "@testing-library/react-native";

import AiConsentScreen from "@/features/auth/screens/AiConsentScreen";
import { AI_CONSENT_ITEMS } from "@/features/auth/model/aiConsent";

const mockAgree = jest.fn();
const mockMergeUser = jest.fn();
const mockSignOut = jest.fn();
const mockWriteCachedUser = jest.fn();
const mockOpenAllowedUrl = jest.fn();
const mockFeedbackError = jest.fn();
let mockAuth: {
  token: string | null;
  user: { id: string; ai_data_consent_at?: string | null } | null;
};

jest.mock("@/lib/haptics", () => ({ tap: jest.fn() }));
jest.mock("expo-router", () => {
  const { Text } = jest.requireActual("react-native");
  return {
    Redirect: ({ href }: { href: string }) => <Text>{`redirect:${href}`}</Text>,
  };
});
jest.mock("expo-linear-gradient", () => {
  const { View } = jest.requireActual("react-native");
  return { LinearGradient: View };
});
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("@/lib/legalUrls", () => ({
  getLegalPrivacyUrl: () => "https://api.test/legal/privacy",
}));
jest.mock("@/lib/linkSchemePolicy", () => ({
  openAllowedUrl: (url: string) => mockOpenAllowedUrl(url),
}));
jest.mock("@/lib/api", () => ({
  agreeToAiDataSharing: (token: string) => mockAgree(token),
}));
jest.mock("@/lib/cachedUser", () => ({
  writeCachedUser: (user: unknown) => mockWriteCachedUser(user),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => ({ error: mockFeedbackError }),
}));
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    ...mockAuth,
    mergeUser: mockMergeUser,
    signOut: mockSignOut,
  }),
}));

describe("AiConsentScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAuth = { token: "tok", user: { id: "u1", ai_data_consent_at: null } };
    mockWriteCachedUser.mockResolvedValue(undefined);
    mockSignOut.mockResolvedValue(undefined);
  });

  it("lists what goes to which outside service, with the privacy policy link", async () => {
    const { getByText } = await render(<AiConsentScreen />);
    expect(getByText("onboarding.consent_title")).toBeOnTheScreen();
    for (const item of AI_CONSENT_ITEMS) {
      expect(getByText(item.titleKey)).toBeOnTheScreen();
      expect(getByText(item.bodyKey)).toBeOnTheScreen();
    }
    fireEvent.press(getByText("onboarding.consent_privacy_link"));
    expect(mockOpenAllowedUrl).toHaveBeenCalledWith("https://api.test/legal/privacy");
  });

  it("stores the agreement on the account and keeps it for the next cold start", async () => {
    const updated = { id: "u1", ai_data_consent_at: "2026-10-19T12:00:00Z" };
    mockAgree.mockResolvedValue(updated);
    const { getByText } = await render(<AiConsentScreen />);

    await act(async () => {
      fireEvent.press(getByText("onboarding.consent_agree"));
    });

    expect(mockAgree).toHaveBeenCalledWith("tok");
    expect(mockMergeUser).toHaveBeenCalledWith(updated);
    expect(mockWriteCachedUser).toHaveBeenCalledWith(updated);
    expect(mockSignOut).not.toHaveBeenCalled();
  });

  it("says so and stays on the screen when the agreement cannot be saved", async () => {
    mockAgree.mockRejectedValue(new Error("offline"));
    const { getByText } = await render(<AiConsentScreen />);

    await act(async () => {
      fireEvent.press(getByText("onboarding.consent_agree"));
    });

    expect(mockFeedbackError).toHaveBeenCalledWith("onboarding.consent_failed");
    expect(mockMergeUser).not.toHaveBeenCalled();
    expect(getByText("onboarding.consent_agree")).toBeOnTheScreen();
  });

  it("signs out when the user says not now, without recording consent", async () => {
    const { getByText } = await render(<AiConsentScreen />);

    await act(async () => {
      fireEvent.press(getByText("onboarding.consent_decline"));
    });

    expect(mockSignOut).toHaveBeenCalledTimes(1);
    expect(mockAgree).not.toHaveBeenCalled();
  });

  it("goes on to the chat when the account has already agreed", async () => {
    mockAuth = { token: "tok", user: { id: "u1", ai_data_consent_at: "2026-10-19T12:00:00Z" } };
    const { getByText, queryByText } = await render(<AiConsentScreen />);
    expect(getByText("redirect:/")).toBeOnTheScreen();
    expect(queryByText("onboarding.consent_agree")).toBeNull();
  });

  it("goes to sign-in when signed out", async () => {
    mockAuth = { token: null, user: null };
    const { getByText } = await render(<AiConsentScreen />);
    expect(getByText("redirect:/login")).toBeOnTheScreen();
  });
});
