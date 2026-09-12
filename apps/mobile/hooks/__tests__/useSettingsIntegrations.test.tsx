import React from "react";
import { Alert } from "react-native";
import { act, render } from "@testing-library/react-native";

import { useSettingsIntegrations } from "@/hooks/useSettingsIntegrations";
import { api, type GoogleCalendarStatus, type GoogleGmailStatus } from "@/lib/api";
import { connectGoogleCalendar } from "@/lib/google-calendar";
import { connectGoogleGmail } from "@/lib/google-gmail";
import { invalidateIntegrationStatusCache, patchIntegrationStatusCache } from "@/lib/cache/integrationStatusCache";
import { invalidateSuggestedRemindersCache } from "@/lib/cache/suggestedRemindersCache";

let mockToken = "account-a";
let mockSession = 1;
jest.mock("expo-router", () => ({ useFocusEffect: jest.fn() }));
jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => null }));
jest.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ token: mockToken }) }));
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));
jest.mock("@/lib/cache/suggestedRemindersCache", () => ({ invalidateSuggestedRemindersCache: jest.fn() }));
jest.mock("@/lib/cache/integrationStatusCache", () => ({
  patchIntegrationStatusCache: jest.fn(), invalidateIntegrationStatusCache: jest.fn(),
}));
jest.mock("@/lib/expoRuntime", () => ({ isExpoGo: () => false }));
jest.mock("@/lib/google-calendar", () => ({ connectGoogleCalendar: jest.fn() }));
jest.mock("@/lib/google-gmail", () => ({ connectGoogleGmail: jest.fn() }));
jest.mock("@/lib/api", () => ({ api: {
  googleCalendarStatus: jest.fn(), googleGmailStatus: jest.fn(),
  disconnectGoogleCalendar: jest.fn(), disconnectGoogleGmail: jest.fn(),
  connectGoogleCalendar: jest.fn(), connectGoogleGmail: jest.fn(), syncGoogleGmail: jest.fn(),
} }));

const CONNECTED = { connected: true, configured: true, email: "a@example.com" };
const DISCONNECTED = { connected: false, configured: true };
const mockApi = jest.mocked(api);
let current: ReturnType<typeof useSettingsIntegrations>;
function Probe() {
  const result = useSettingsIntegrations();
  React.useLayoutEffect(() => { current = result; });
  return null;
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
async function mount() {
  const view = await render(<Probe />);
  await act(async () => { await current.refresh(); });
  return view;
}
function confirmation() {
  return jest.mocked(Alert.alert).mock.calls.at(-1)?.[2]?.find(
    (button) => button.style === "destructive",
  )?.onPress as () => Promise<void>;
}

beforeEach(() => {
  jest.resetAllMocks();
  mockToken = "account-a";
  mockSession++;
  mockApi.googleCalendarStatus.mockResolvedValue(CONNECTED);
  mockApi.googleGmailStatus.mockResolvedValue(CONNECTED);
  mockApi.connectGoogleCalendar.mockResolvedValue(CONNECTED);
  mockApi.connectGoogleGmail.mockResolvedValue(CONNECTED);
  mockApi.disconnectGoogleCalendar.mockResolvedValue(undefined);
  mockApi.disconnectGoogleGmail.mockResolvedValue(undefined);
  mockApi.syncGoogleGmail.mockResolvedValue({ status: "ok", message_count: 0, reminders_created: 0 });
  jest.mocked(connectGoogleCalendar).mockResolvedValue("calendar-code");
  jest.mocked(connectGoogleGmail).mockResolvedValue("gmail-code");
  jest.spyOn(Alert, "alert").mockImplementation(() => {});
});

it("keeps unknown statuses indeterminate and blocks consent until the initial status load finishes", async () => {
  await render(<Probe />);
  expect(current).toMatchObject({ loading: true, calendarStatus: null, gmailStatus: null });
  await act(async () => { await current.connectCalendar(); await current.connectGmail(); });
  expect(connectGoogleCalendar).not.toHaveBeenCalled();
  expect(connectGoogleGmail).not.toHaveBeenCalled();
  await act(async () => { await current.refresh(); });
  expect(current.loading).toBe(false);
});

it("opens Gmail consent directly and preserves its connected state if the first sync fails", async () => {
  mockApi.googleGmailStatus.mockResolvedValue(DISCONNECTED);
  mockApi.syncGoogleGmail.mockRejectedValue(new Error("Sync unavailable"));
  await mount();
  await act(async () => { await current.connectGmail(); });
  expect(connectGoogleGmail).toHaveBeenCalledTimes(1);
  expect(mockApi.connectGoogleGmail).toHaveBeenCalledWith("account-a", "gmail-code");
  expect(current.gmailStatus).toEqual(CONNECTED);
  expect(current.gmailBusy).toBe(false);
  expect(patchIntegrationStatusCache).toHaveBeenCalledWith({ gmailConnected: true });
  expect(Alert.alert).toHaveBeenCalledTimes(1);
  expect(Alert.alert).toHaveBeenCalledWith("settings.gmail_title", "Sync unavailable");
});

it("serializes same-frame duplicate taps and both services against the shared native Google session", async () => {
  const consent = deferred<string>();
  jest.mocked(connectGoogleCalendar).mockReturnValue(consent.promise);
  await mount();
  let connecting!: Promise<void>;
  await act(async () => {
    connecting = current.connectCalendar();
    await current.connectCalendar(); await current.connectGmail(); await current.syncGmail();
  });
  expect(current.calendarBusy).toBe(true);
  expect(connectGoogleCalendar).toHaveBeenCalledTimes(1);
  expect(connectGoogleGmail).not.toHaveBeenCalled();
  expect(mockApi.syncGoogleGmail).not.toHaveBeenCalled();
  await act(async () => { consent.resolve("new-code"); await connecting; });
  expect(mockApi.connectGoogleCalendar).toHaveBeenCalledTimes(1);
  expect(current.calendarBusy).toBe(false);
});

it("warns about sibling disconnect and refreshes both statuses after Calendar disconnect", async () => {
  await mount();
  mockApi.googleCalendarStatus.mockResolvedValue(DISCONNECTED);
  mockApi.googleGmailStatus.mockResolvedValue(DISCONNECTED);
  await act(async () => { current.disconnectCalendar(); });
  expect(Alert.alert).toHaveBeenCalledWith(
    "settings.calendar_title", "settings.calendar_disconnect_confirm", expect.any(Array),
  );
  await act(async () => { await confirmation()(); });
  expect(mockApi.disconnectGoogleCalendar).toHaveBeenCalledWith("account-a");
  expect(invalidateSuggestedRemindersCache).toHaveBeenCalled();
  expect(invalidateIntegrationStatusCache).toHaveBeenCalled();
  expect(current.calendarStatus?.connected).toBe(false);
  expect(current.gmailStatus?.connected).toBe(false);
  expect(patchIntegrationStatusCache).toHaveBeenLastCalledWith({ calendarConnected: false, gmailConnected: false });
});

it("rechecks the shared operation lock when a disconnect confirmation is accepted", async () => {
  const sync = deferred<{ status: string; message_count: number; reminders_created: number }>();
  mockApi.syncGoogleGmail.mockReturnValue(sync.promise);
  await mount();
  await act(async () => { current.disconnectCalendar(); });
  const confirm = confirmation();
  let syncing!: Promise<void>;
  await act(async () => { syncing = current.syncGmail(); await confirm(); });
  expect(mockApi.disconnectGoogleCalendar).not.toHaveBeenCalled();
  await act(async () => {
    sync.resolve({ status: "ok", message_count: 0, reminders_created: 0 });
    await syncing;
  });
});

it("keeps successful disconnect visible and treats the sibling as unknown if status refresh fails", async () => {
  await mount();
  mockApi.googleCalendarStatus.mockRejectedValue(new Error("offline"));
  mockApi.googleGmailStatus.mockRejectedValue(new Error("offline"));
  await act(async () => { current.disconnectCalendar(); await confirmation()(); });
  expect(current.calendarStatus?.connected).toBe(false);
  expect(current.gmailStatus).toBeNull();
  expect(current).toMatchObject({ loadError: true, calendarBusy: false });
  await act(async () => { await current.connectGmail(); });
  expect(connectGoogleGmail).not.toHaveBeenCalled();
});

it("ignores an older refresh that completes after a newer snapshot", async () => {
  await mount();
  const calendar = deferred<GoogleCalendarStatus>();
  const gmail = deferred<GoogleGmailStatus>();
  mockApi.googleCalendarStatus.mockReturnValueOnce(calendar.promise).mockResolvedValueOnce(DISCONNECTED);
  mockApi.googleGmailStatus.mockReturnValueOnce(gmail.promise).mockResolvedValueOnce(DISCONNECTED);
  let first!: Promise<void>;
  await act(async () => { first = current.refresh(); await current.refresh(); });
  await act(async () => { calendar.resolve(CONNECTED); gmail.resolve(CONNECTED); await first; });
  expect(current.calendarStatus?.connected).toBe(false);
  expect(current.gmailStatus?.connected).toBe(false);
  expect(patchIntegrationStatusCache).toHaveBeenLastCalledWith({ calendarConnected: false, gmailConnected: false });
});

it("skips background refresh while a mutation owns the connection state", async () => {
  const consent = deferred<string>();
  jest.mocked(connectGoogleCalendar).mockReturnValue(consent.promise);
  await mount();
  let connecting!: Promise<void>;
  await act(async () => { connecting = current.connectCalendar(); await current.refresh(); });
  expect(mockApi.googleCalendarStatus).toHaveBeenCalledTimes(1);
  await act(async () => { consent.resolve("code"); await connecting; });
  expect(current.calendarStatus?.connected).toBe(true);
});

it("hides previous-account statuses and ignores old refresh responses after switching accounts", async () => {
  const view = await mount();
  const calendar = deferred<GoogleCalendarStatus>();
  const gmail = deferred<GoogleGmailStatus>();
  mockApi.googleCalendarStatus.mockReturnValueOnce(calendar.promise);
  mockApi.googleGmailStatus.mockReturnValueOnce(gmail.promise);
  let pending!: Promise<void>;
  await act(async () => { pending = current.refresh(); });
  mockSession++;
  mockToken = "account-b";
  await view.rerender(<Probe />);
  expect(current).toMatchObject({ calendarStatus: null, gmailStatus: null, loading: true });
  mockApi.googleCalendarStatus.mockResolvedValue(DISCONNECTED);
  mockApi.googleGmailStatus.mockResolvedValue(DISCONNECTED);
  await act(async () => { await current.refresh(); });
  await act(async () => { calendar.resolve(CONNECTED); gmail.resolve(CONNECTED); await pending; });
  expect(current.calendarStatus).toEqual(DISCONNECTED);
  expect(current.gmailStatus).toEqual(DISCONNECTED);
  expect(patchIntegrationStatusCache).toHaveBeenLastCalledWith({ calendarConnected: false, gmailConnected: false });
});

it("rejects retained consent and disconnect callbacks after the session changes", async () => {
  await mount();
  await act(async () => { current.disconnectCalendar(); });
  const confirm = confirmation();
  const previous = current;
  mockSession++;
  await act(async () => {
    await confirm(); await previous.connectCalendar(); await previous.connectGmail(); await previous.syncGmail();
  });
  expect(mockApi.disconnectGoogleCalendar).not.toHaveBeenCalled();
  expect(connectGoogleCalendar).not.toHaveBeenCalled();
  expect(connectGoogleGmail).not.toHaveBeenCalled();
  expect(mockApi.syncGoogleGmail).not.toHaveBeenCalled();
});

it("does not exchange a late consent code or show errors after unmount", async () => {
  const consent = deferred<string>();
  jest.mocked(connectGoogleGmail).mockReturnValue(consent.promise);
  const view = await mount();
  let connecting!: Promise<void>;
  await act(async () => { connecting = current.connectGmail(); });
  await view.unmount();
  await act(async () => { consent.resolve("late-code"); await connecting; });
  expect(mockApi.connectGoogleGmail).not.toHaveBeenCalled();
  expect(Alert.alert).not.toHaveBeenCalled();
});

it("does not let a stale operation error unlock a new account's operation", async () => {
  const oldConsent = deferred<string>();
  const newConsent = deferred<string>();
  jest.mocked(connectGoogleCalendar).mockReturnValueOnce(oldConsent.promise).mockReturnValueOnce(newConsent.promise);
  const view = await mount();
  let previous!: Promise<void>;
  await act(async () => { previous = current.connectCalendar(); });
  mockSession++;
  mockToken = "account-b";
  await view.rerender(<Probe />);
  await act(async () => { await current.refresh(); });
  let next!: Promise<void>;
  await act(async () => { next = current.connectCalendar(); });
  await act(async () => { oldConsent.reject(new Error("old failure")); await previous; });
  expect(current.calendarBusy).toBe(true);
  expect(Alert.alert).not.toHaveBeenCalled();
  await act(async () => { newConsent.resolve("new-code"); await next; });
  expect(current.calendarBusy).toBe(false);
});
