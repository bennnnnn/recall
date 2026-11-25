import { Linking } from "react-native";
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
jest.mock("expo-router", () => ({ Redirect: () => null, useFocusEffect: () => {}, router: { push: jest.fn() } }));
jest.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ user: mockUser, token: "tok" }) }));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => null }));
jest.mock("@/features/account/hooks/useUsage", () => ({ useUsage: () => ({ usage: null }) }));
let mockStorage: { usedBytes: number; limitBytes: number } | null = null;
jest.mock("@/features/account/hooks/useLibraryStorage", () => ({
  useLibraryStorage: () => mockStorage,
}));
jest.mock("@/features/billing/components/UpgradeSheet", () => ({
  UpgradeSheet: ({ visible }: { visible: boolean }) => {
    mockUpgradeVisible = visible;
    return null;
  },
}));

const PAID = ["all_models", "image_generation", "speech_transcription", "speech_tts"];

beforeEach(() => {
  mockUpgradeVisible = false;
  mockStorage = null;
});

it("free: names the plan and opens the plans sheet", async () => {
  mockUser = { email: "a@b.c", plan: "free", features: ["image_generation"] };
  const screen = await render(<AccountSettingsSection />);
  expect(screen.getByText("plans.free")).toBeOnTheScreen();
  expect(screen.queryByText(/settings\.live_talk_minutes_left/)).toBeNull();
  await fireEvent.press(screen.getByText("plans.free"));
  expect(mockUpgradeVisible).toBe(true);
});

it("paid: the plan is named on its own row, and Manage subscription is a row of its own", async () => {
  const openURL = jest.spyOn(Linking, "openURL").mockResolvedValue(undefined);
  mockUser = { email: "a@b.c", plan: "pro", features: [...PAID, "live_talk"] };
  const screen = await render(<AccountSettingsSection />);
  // The email row says who is signed in; how they signed in is not repeated under it.
  expect(screen.queryByText(/settings\.signed_in_with/)).toBeNull();
  // Tapping the plan opens nothing; the store opens from its own row.
  await fireEvent.press(screen.getByText("plans.pro"));
  expect(openURL).not.toHaveBeenCalled();
  await fireEvent.press(screen.getByText("settings.manage_subscription"));
  expect(openURL).toHaveBeenCalledTimes(1);
  openURL.mockRestore();
});

it("Pro: usage is a row that opens its own page", async () => {
  mockUser = { email: "a@b.c", plan: "pro", features: [...PAID, "live_talk"] };
  const screen = await render(<AccountSettingsSection />);
  expect(screen.getByText("plans.pro")).toBeOnTheScreen();
  expect(screen.getByText("settings.usage_group")).toBeOnTheScreen();
  expect(screen.queryByText(/settings\.live_talk_minutes_left/)).toBeNull();
});

it("Storage says what Library keeps of the plan's total, and opens Library", async () => {
  const { router } = jest.requireMock("expo-router") as { router: { push: jest.Mock } };
  mockUser = { email: "a@b.c", plan: "free", features: ["image_generation"] };
  mockStorage = { usedBytes: 123 * 1024 ** 2, limitBytes: 400 * 1024 ** 2 };
  const screen = await render(<AccountSettingsSection />);
  expect(screen.getByText(/settings\.storage_value/)).toBeOnTheScreen();
  await fireEvent.press(screen.getByText("settings.storage"));
  expect(router.push).toHaveBeenCalledWith("/gallery");
});

it("Storage shows no number before the server answers", async () => {
  mockUser = { email: "a@b.c", plan: "pro", features: [...PAID] };
  const screen = await render(<AccountSettingsSection />);
  expect(screen.getByText("settings.storage")).toBeOnTheScreen();
  expect(screen.queryByText(/settings\.storage_value/)).toBeNull();
});
