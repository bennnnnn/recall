import { fireEvent, render } from "@testing-library/react-native";

import ConnectedAppsScreen from "@/app/settings/integrations";
import type { useSettingsIntegrations } from "@/hooks/useSettingsIntegrations";

let mockIntegrations: ReturnType<typeof useSettingsIntegrations>;

jest.mock("@expo/vector-icons", () => ({ Ionicons: "Ionicons" }));
jest.mock("expo-router", () => ({ Redirect: () => null }));
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
jest.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ token: "token" }) }));
jest.mock("@/hooks/useSettingsIntegrations", () => ({ useSettingsIntegrations: () => mockIntegrations }));
jest.mock("@/lib/haptics", () => ({ tap: jest.fn() }));

beforeEach(() => {
  mockIntegrations = {
    calendarStatus: { connected: false, configured: true },
    gmailStatus: { connected: false, configured: true },
    calendarBusy: false,
    gmailBusy: false,
    loading: false,
    loadError: false,
    connectedCount: 0,
    connectCalendar: jest.fn(async () => undefined),
    disconnectCalendar: jest.fn(),
    connectGmail: jest.fn(),
    disconnectGmail: jest.fn(),
    syncGmail: jest.fn(async () => undefined),
    refresh: jest.fn(async () => undefined),
  };
});

it("connects either provider directly from its visible card", async () => {
  const view = await render(<ConnectedAppsScreen />);
  expect(view.getByText("Google Calendar")).toBeTruthy();
  expect(view.getByText("Gmail")).toBeTruthy();
  await fireEvent.press(view.getByRole("button", { name: "Connect Google Calendar" }));
  expect(mockIntegrations.connectCalendar).toHaveBeenCalledWith(false);
  await fireEvent.press(view.getByRole("button", { name: "Connect Gmail" }));
  expect(mockIntegrations.connectGmail).toHaveBeenCalledTimes(1);
});

it("keeps accounts, permissions, sync and disconnect on the same page", async () => {
  mockIntegrations.calendarStatus = { connected: true, configured: true, email: "calendar@example.com", can_write: false };
  mockIntegrations.gmailStatus = { connected: true, configured: true, email: "gmail@example.com", last_sync_at: "2026-09-12T12:00:00Z" };
  const view = await render(<ConnectedAppsScreen />);
  expect(view.getByText("calendar@example.com")).toBeTruthy();
  expect(view.getByText("gmail@example.com")).toBeTruthy();
  await fireEvent.press(view.getByText("Enable write access"));
  expect(mockIntegrations.connectCalendar).toHaveBeenCalledWith(true);
  await fireEvent.press(view.getByText("Sync"));
  expect(mockIntegrations.syncGmail).toHaveBeenCalledTimes(1);
  await fireEvent.press(view.getByRole("button", { name: "Disconnect Google Calendar" }));
  expect(mockIntegrations.disconnectCalendar).toHaveBeenCalledTimes(1);
  await fireEvent.press(view.getByRole("button", { name: "Disconnect Gmail" }));
  expect(mockIntegrations.disconnectGmail).toHaveBeenCalledTimes(1);
});

it("does not call a connected account disconnected when its email is missing", async () => {
  mockIntegrations.calendarStatus = { connected: true, configured: true, can_write: true };
  const view = await render(<ConnectedAppsScreen />);
  expect(view.getByText("Connected")).toBeTruthy();
  expect(view.queryByText("Enable write access")).toBeNull();
  expect(view.getByRole("button", { name: "Disconnect Google Calendar" })).toBeTruthy();
});

it("keeps unknown connections indeterminate and prevents premature consent", async () => {
  mockIntegrations.calendarStatus = null;
  mockIntegrations.gmailStatus = null;
  mockIntegrations.loading = true;
  const view = await render(<ConnectedAppsScreen />);
  expect(view.queryByText("Not connected")).toBeNull();
  const calendar = view.getByRole("button", { name: "Connect Google Calendar" });
  expect(calendar.props.accessibilityState).toEqual({ busy: true, disabled: true });
  await fireEvent.press(calendar);
  expect(mockIntegrations.connectCalendar).not.toHaveBeenCalled();
});

it("prevents overlapping provider actions while a connection is busy", async () => {
  mockIntegrations.calendarBusy = true;
  const view = await render(<ConnectedAppsScreen />);
  const gmail = view.getByRole("button", { name: "Connect Gmail" });
  expect(gmail.props.accessibilityState.disabled).toBe(true);
  await fireEvent.press(gmail);
  expect(mockIntegrations.connectGmail).not.toHaveBeenCalled();
});

it("offers retry when status is unavailable without enabling Connect", async () => {
  mockIntegrations.calendarStatus = null;
  mockIntegrations.loadError = true;
  const view = await render(<ConnectedAppsScreen />);
  expect(view.getByRole("button", { name: "Connect Google Calendar" }).props.accessibilityState.disabled).toBe(true);
  await fireEvent.press(view.getByText("Retry"));
  expect(mockIntegrations.refresh).toHaveBeenCalledTimes(1);
});
