import { fireEvent, render } from "@testing-library/react-native";

import HelpScreen from "@/features/account/screens/HelpScreen";

const mockOpenUrl = jest.fn();
const mockConfig: { supportEmail: string | null } = { supportEmail: null };

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
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
jest.mock("@/lib/linkSchemePolicy", () => ({
  openAllowedUrl: (...args: unknown[]) => mockOpenUrl(...args),
}));

beforeEach(() => {
  jest.clearAllMocks();
  mockConfig.supportEmail = null;
});

it("offers support, a problem report and feedback, and none of the legal pages", async () => {
  const view = await render(<HelpScreen />);
  expect(view.getByText("settings.report_problem")).toBeTruthy();
  expect(view.getByText("settings.send_feedback")).toBeTruthy();
  expect(view.queryByText("privacy.title")).toBeNull();
});

it("hides Contact support until a support address is configured", async () => {
  const view = await render(<HelpScreen />);
  expect(view.queryByText("settings.contact_support")).toBeNull();
});

it("writes to the configured support address", async () => {
  mockConfig.supportEmail = "help@recall.test";
  const view = await render(<HelpScreen />);
  await fireEvent.press(view.getByText("settings.contact_support"));
  const url = mockOpenUrl.mock.calls[0][0] as string;
  expect(url.startsWith("mailto:help@recall.test?subject=settings.contact_support_subject")).toBe(true);
  expect(decodeURIComponent(url)).toContain("settings.about_version: 2.3.4");
});
