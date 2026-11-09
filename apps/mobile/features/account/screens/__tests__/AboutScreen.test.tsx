import { act, fireEvent, render } from "@testing-library/react-native";
import { setStringAsync } from "expo-clipboard";

import AboutScreen from "@/features/account/screens/AboutScreen";

const mockOpenUrl = jest.fn();
const mockReportError = jest.fn();
const mockConfig: { supportEmail: string | null } = { supportEmail: null };

jest.mock("expo-constants", () => ({ expoConfig: { version: "2.3.4" } }));
// This build runs an over-the-air update.
jest.mock("@/lib/appVersion", () => ({
  ...jest.requireActual("@/lib/appVersion"),
  appVersion: () => ({ version: "2.3.4", build: null, update: "ab12cd34" }),
}));
jest.mock("expo-router", () => ({ Redirect: () => null, router: { push: jest.fn() } }));
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "tok", user: { locale: "en" } }),
}));
const mockFeedback = { success: jest.fn() };
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => mockFeedback }));
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

it("shows the legal pages, the licenses and the version, and no help rows", async () => {
  const view = await render(<AboutScreen />);
  expect(view.getByText("privacy.title")).toBeTruthy();
  expect(view.getByText("terms.title")).toBeTruthy();
  expect(view.getByText("settings.licenses")).toBeTruthy();
  expect(view.getByText("2.3.4")).toBeTruthy();
  expect(view.queryByText("settings.report_problem")).toBeNull();
  expect(view.queryByText("UI kit")).toBeNull();
});

it("opens the privacy policy", async () => {
  mockOpenUrl.mockResolvedValue(true);
  const view = await render(<AboutScreen />);
  await act(async () => {
    fireEvent.press(view.getByText("privacy.title"));
  });
  expect(mockOpenUrl).toHaveBeenCalledWith("https://recall.test/privacy");
  expect(mockReportError).not.toHaveBeenCalled();
});

it("says so when a legal page cannot be opened", async () => {
  mockOpenUrl.mockResolvedValue(false);
  const view = await render(<AboutScreen />);
  await act(async () => {
    fireEvent.press(view.getByText("terms.title"));
  });
  expect(mockReportError).toHaveBeenCalledWith(mockFeedback, "settings.link_failed");
});

// About showed the over-the-air update's internal id as a row of its own.
it("keeps the update id off the page and copies it with the version on a long press", async () => {
  const view = await render(<AboutScreen />);
  expect(view.queryByText("settings.about_update")).toBeNull();
  expect(view.queryByText("ab12cd34")).toBeNull();
  await act(async () => {
    fireEvent(view.getByText("2.3.4"), "longPress");
  });
  expect(setStringAsync).toHaveBeenCalledWith("settings.about_version: 2.3.4\nsettings.about_update: ab12cd34");
  expect(mockFeedback.success).toHaveBeenCalledWith("common.copied");
});
