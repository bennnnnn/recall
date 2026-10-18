import { fireEvent, render } from "@testing-library/react-native";

import { AccountSettingsSection } from "@/features/account/components/AccountSettingsSection";

let mockUser: { email: string; plan: string; features?: string[] } = {
  email: "a@b.c",
  plan: "free",
};
let mockUpgradeVisible = false;

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) =>
      options ? `${key} ${JSON.stringify(options)}` : key,
  }),
}));
jest.mock("expo-router", () => ({ Redirect: () => null, router: { push: jest.fn() } }));
jest.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ user: mockUser, token: "tok" }) }));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => null }));
jest.mock("@/features/account/hooks/useUsage", () => ({ useUsage: () => ({ usage: null }) }));
jest.mock("@/features/account/hooks/useLiveTalkMinutes", () => ({
  useLiveTalkMinutes: (enabled: boolean) => (enabled ? { remaining: 42, limit: 60 } : null),
}));
jest.mock("@/components/UpgradeSheet", () => ({
  UpgradeSheet: ({ visible }: { visible: boolean }) => {
    mockUpgradeVisible = visible;
    return null;
  },
}));

const PAID = ["all_models", "image_generation", "speech_transcription", "speech_tts"];

beforeEach(() => {
  mockUpgradeVisible = false;
});

it("free: names the plan and opens the plans sheet", async () => {
  mockUser = { email: "a@b.c", plan: "free", features: ["image_generation"] };
  const screen = await render(<AccountSettingsSection isPaid={false} />);
  expect(screen.getByText("plans.free")).toBeOnTheScreen();
  expect(screen.queryByText(/settings\.plan_upgrade/)).toBeNull();
  expect(screen.queryByText(/settings\.usage_live_talk/)).toBeNull();
  await fireEvent.press(screen.getByText("plans.free"));
  expect(mockUpgradeVisible).toBe(true);
});

it("Plus: manages the subscription and offers the step up to Pro", async () => {
  mockUser = { email: "a@b.c", plan: "plus", features: PAID };
  const screen = await render(<AccountSettingsSection isPaid />);
  expect(screen.getByText("plans.plus")).toBeOnTheScreen();
  expect(screen.getByText("settings.manage_subscription")).toBeOnTheScreen();
  expect(screen.queryByText(/settings\.usage_live_talk/)).toBeNull();
  await fireEvent.press(screen.getByText('settings.plan_upgrade {"plan":"plans.pro"}'));
  expect(mockUpgradeVisible).toBe(true);
});

it("Pro: shows this month's live talk minutes under Usage and no upgrade row", async () => {
  mockUser = { email: "a@b.c", plan: "pro", features: [...PAID, "live_talk"] };
  const screen = await render(<AccountSettingsSection isPaid />);
  expect(screen.getByText("plans.pro")).toBeOnTheScreen();
  expect(screen.getByText("settings.usage_group")).toBeOnTheScreen();
  expect(
    screen.getByText('settings.usage_live_talk {"count":42,"limit":60}'),
  ).toBeOnTheScreen();
  expect(screen.queryByText(/settings\.plan_upgrade/)).toBeNull();
});
