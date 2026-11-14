import { fireEvent, render } from "@testing-library/react-native";

import UsageScreen from "@/features/account/screens/UsageScreen";

let mockUser: Record<string, unknown>;
let mockUsage: Record<string, unknown>;
const mockRefresh = jest.fn();

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) =>
      options ? `${key} ${JSON.stringify(options)}` : key,
  }),
}));
jest.mock("expo-router", () => ({ Redirect: () => null, router: { push: jest.fn() } }));
jest.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ token: "tok", user: mockUser }) }));
jest.mock("@/features/account/hooks/useUsage", () => ({ useUsage: () => mockUsage }));
jest.mock("@/lib/quota", () => ({ formatUsageSummary: () => "80% of today's limit left" }));

beforeEach(() => {
  jest.clearAllMocks();
  mockUser = { plan: "pro", features: ["all_models", "live_talk"] };
  mockUsage = { usage: { remaining: 8, daily_limit: 10 }, loading: false, error: false, refresh: mockRefresh };
});

it("shows the messages left today, and no separate live talk count", async () => {
  const view = await render(<UsageScreen />);
  expect(view.getByText("80% of today's limit left")).toBeTruthy();
  // Pro has live talk; Usage still shows only today's messages (the owner's call, 2026-11-11).
  expect(view.queryByText(/live_talk/)).toBeNull();
});

it("offers a retry when today's usage would not load", async () => {
  mockUsage = { usage: null, loading: false, error: true, refresh: mockRefresh };
  const view = await render(<UsageScreen />);
  await fireEvent.press(view.getByText("settings.usage_unavailable"));
  expect(mockRefresh).toHaveBeenCalledWith({ force: true });
});
