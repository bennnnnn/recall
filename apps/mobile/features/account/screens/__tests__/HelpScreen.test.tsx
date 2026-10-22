import { act, fireEvent, render } from "@testing-library/react-native";

import HelpScreen from "@/features/account/screens/HelpScreen";

const mockOpenUrl = jest.fn();
const mockReportError = jest.fn();
const mockConfig: { supportEmail: string | null } = { supportEmail: null };

jest.mock("expo-constants", () => ({ expoConfig: { version: "2.3.4" } }));
jest.mock("expo-router", () => ({ Redirect: () => null, router: { push: jest.fn() } }));
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "tok", user: { locale: "en" } }),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => null }));
jest.mock("@/hooks/useModels", () => ({ useModels: () => ({ isPaid: false }) }));
jest.mock("@/lib/config", () => ({
  get config() {
    return mockConfig;
  },
}));
jest.mock("@/lib/legalUrls", () => ({
  getLegalPrivacyUrl: () => "https://recall.test/privacy",
  getLegalTermsUrl: () => "https://recall.test/terms",
}));
jest.mock("@/lib/reportRecoverableError", () => ({
  reportRecoverableError: (...args: unknown[]) => mockReportError(...args),
}));
jest.mock("@/lib/linkSchemePolicy", () => ({
  openAllowedUrl: (...args: unknown[]) => mockOpenUrl(...args),
}));

beforeEach(() => {
  jest.clearAllMocks();
  mockConfig.supportEmail = null;
});

it("writes every help row to the support address, and no legal pages", async () => {
  mockConfig.supportEmail = "help@recall.test";
  mockOpenUrl.mockResolvedValue(true);
  const view = await render(<HelpScreen />);
  expect(view.queryByText("privacy.title")).toBeNull();
  for (const row of ["settings.contact_support", "settings.report_problem", "settings.send_feedback"]) {
    mockOpenUrl.mockClear();
    await act(async () => {
      fireEvent.press(view.getByText(row));
    });
    const url = mockOpenUrl.mock.calls[0][0] as string;
    expect(url.startsWith("mailto:help@recall.test?subject=")).toBe(true);
    expect(decodeURIComponent(url)).toContain(`settings.contact_support_subject: ${row}`);
    expect(decodeURIComponent(url)).toContain("settings.about_version: 2.3.4");
  }
});

it("says support is not set up, instead of a share sheet that reaches nobody", async () => {
  const view = await render(<HelpScreen />);
  expect(view.getByText("settings.support_unavailable")).toBeTruthy();
  expect(view.queryByText("settings.contact_support")).toBeNull();
  expect(view.queryByText("settings.report_problem")).toBeNull();
  expect(view.queryByText("settings.send_feedback")).toBeNull();
});

it("says so when the mail app cannot be opened", async () => {
  mockConfig.supportEmail = "help@recall.test";
  mockOpenUrl.mockResolvedValue(false);
  const view = await render(<HelpScreen />);
  await act(async () => {
    fireEvent.press(view.getByText("settings.report_problem"));
  });
  expect(mockReportError).toHaveBeenCalledWith(null, "settings.link_failed");
});
