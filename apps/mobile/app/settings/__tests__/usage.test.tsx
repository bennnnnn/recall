import { fireEvent, render } from "@testing-library/react-native";

import UsageSettingsScreen from "@/app/settings/usage";
import type { Usage } from "@/lib/api";

const mockRefresh = jest.fn();
let mockUsage: Usage | null;
let mockError = false;
let mockPlan = "free";

jest.mock("@expo/vector-icons", () => ({ Ionicons: "Ionicons" }));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) => {
      const en = jest.requireActual<Record<string, string>>("@/lib/i18n/en.json");
      return (en[key] ?? key).replace(/{{(\w+)}}/g, (_, name) => String(options?.[name] ?? ""));
    },
  }),
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 12, left: 0, right: 0 }),
}));
jest.mock("expo-router", () => ({ Redirect: () => null }));
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "token", user: { plan: mockPlan } }),
}));
jest.mock("@/hooks/useUsage", () => ({
  useUsage: () => ({
    usage: mockUsage,
    loading: !mockUsage && !mockError,
    error: mockError,
    refresh: mockRefresh,
  }),
}));
jest.mock("@/lib/haptics", () => ({ tap: jest.fn() }));

beforeEach(() => {
  mockRefresh.mockReset().mockResolvedValue(undefined);
  mockError = false;
  mockPlan = "free";
  mockUsage = {
    date: "2026-09-12",
    input_tokens: 8000,
    output_tokens: 4000,
    used_tokens: 12000,
    daily_limit: 100000,
    remaining: 88000,
  };
});

it("shows weighted daily use and an accessible bounded progress bar", async () => {
  const { getByText, getByRole } = await render(<UsageSettingsScreen />);
  expect(getByText("12,000 / 100,000")).toBeTruthy();
  expect(getByText("88% of today's free limit left")).toBeTruthy();
  expect(getByRole("progressbar").props.accessibilityValue).toEqual({
    min: 0, max: 100, now: 12, text: "12,000 / 100,000",
  });
});

it.each([
  { used: 0, limit: 100000, remaining: 100000, percent: 0 },
  { used: 120000, limit: 100000, remaining: 0, percent: 100 },
  { used: 0, limit: 0, remaining: 0, percent: 0 },
])("handles usage bounds $used/$limit", async ({ used, limit, remaining, percent }) => {
  mockUsage = { ...mockUsage!, used_tokens: used, daily_limit: limit, remaining };
  const { getByRole } = await render(<UsageSettingsScreen />);
  expect(getByRole("progressbar").props.accessibilityValue.now).toBe(percent);
});

it("shows Pro limit information without a free-plan upgrade message", async () => {
  mockPlan = "pro";
  mockUsage = { ...mockUsage!, remaining: 0, used_tokens: 100000 };
  const { getByText, queryByText } = await render(<UsageSettingsScreen />);
  expect(getByText("0% left today — try again after midnight UTC.")).toBeTruthy();
  expect(queryByText(/go Pro/)).toBeNull();
});

it("never reports an unloaded value as zero usage", async () => {
  mockUsage = null;
  const { getByRole, queryByText } = await render(<UsageSettingsScreen />);
  const loading = getByRole("progressbar");
  expect(loading.props.accessibilityState).toEqual({ busy: true });
  expect(loading.props.accessibilityValue).toBeUndefined();
  expect(queryByText(/0 \/ 0/)).toBeNull();
  expect(queryByText(/limit left/)).toBeNull();
});

it("offers a forced retry after a failed fetch instead of displaying cached values", async () => {
  mockError = true;
  const { getByText, queryByText, queryByRole } = await render(<UsageSettingsScreen />);
  expect(queryByRole("progressbar")).toBeNull();
  expect(queryByText("12,000 / 100,000")).toBeNull();
  await fireEvent.press(getByText("Retry"));
  expect(mockRefresh).toHaveBeenCalledWith({ force: true });
});
