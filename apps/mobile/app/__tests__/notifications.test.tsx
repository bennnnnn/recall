import { Alert } from "react-native";
import { act, render } from "@testing-library/react-native";
import NotificationsSettingsScreen from "@/app/settings/notifications";
import { cancelAllTodoReminders, syncTodoReminders } from "@/lib/todos/todoReminders";
import { ensureNotificationPermission, registerRemotePushToken, unregisterRemotePushToken } from "@/lib/pushNotifications";

let mockSession = 0;
let mockFocused = true;
const mockUpdate = jest.fn();
const mockFeedback = { error: jest.fn() };
const mockT = (key: string) => key;
const mockSwitches: Record<string, { onValueChange: (value: boolean) => Promise<void>; disabled: boolean }> = {};
let mockPicker: { onSelect: (key: string) => void };
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));
jest.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ token: "token", user: {
  id: "user", reminder_lead_minutes: 10, push_notifications_enabled: false,
}, updateUser: mockUpdate }) }));
jest.mock("@/contexts/TodosContext", () => ({ useTodos: () => ({ todos: [{ id: "stale-row" }] }) }));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => mockFeedback }));
jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: mockT }) }));
jest.mock("react-native-safe-area-context", () => ({ useSafeAreaInsets: () => ({ bottom: 0 }) }));
jest.mock("@/lib/theme", () => ({ useTheme: () => ({}) }));
jest.mock("@/components/settings/settingsUi", () => ({
  makeSettingsStyles: () => ({}), SettingsGroup: ({ children }: { children: React.ReactNode }) => children,
  SettingsSwitchRow: (props: { title: string } & (typeof mockSwitches)[string]) => { mockSwitches[props.title] = props; return null; },
  SettingsInlinePicker: (props: typeof mockPicker) => { mockPicker = props; return null; },
}));
jest.mock("@/lib/reminderPrefs", () => ({
  DEFAULT_REMINDER_LEAD_MINUTES: 10, REMINDER_LEAD_OPTIONS: [0, 10, 30],
  getReminderLeadMinutes: jest.fn(async () => 10), setReminderLeadMinutes: jest.fn(async () => undefined),
  syncReminderLeadFromServer: jest.fn(async () => 10),
}));
jest.mock("@/lib/todos/todoReminders", () => ({ cancelAllTodoReminders: jest.fn(), syncTodoReminders: jest.fn() }));
jest.mock("@/lib/pushNotifications", () => ({
  ensureNotificationPermission: jest.fn(async () => true), registerRemotePushToken: jest.fn(async () => undefined),
  unregisterRemotePushToken: jest.fn(async () => undefined),
}));
jest.mock("expo-router", () => ({ Redirect: () => null,
  useFocusEffect: (effect: () => void | (() => void)) => {
    const React = jest.requireActual("react");
    const focused = mockFocused;
    React.useEffect(() => focused ? effect() : undefined, [effect, focused]);
  },
}));
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}
beforeEach(() => {
  jest.clearAllMocks(); mockSession++; mockFocused = true; mockUpdate.mockResolvedValue(undefined);
  jest.spyOn(Alert, "alert").mockImplementation(() => {});
});

it("never resyncs a captured todo list after a delayed settings save", async () => {
  const saving = deferred<void>();
  mockUpdate.mockReturnValueOnce(saving.promise);
  await render(<NotificationsSettingsScreen />);
  await act(() => { mockPicker.onSelect("30"); });
  await act(async () => { saving.resolve(); });
  expect(mockUpdate).toHaveBeenCalledWith({ reminder_lead_minutes: 30 });
  expect(syncTodoReminders).not.toHaveBeenCalled();
  expect(cancelAllTodoReminders).not.toHaveBeenCalled();
});

it("does not register push or change the next account after delayed permission", async () => {
  const permission = deferred<boolean>();
  jest.mocked(ensureNotificationPermission).mockReturnValueOnce(permission.promise);
  await render(<NotificationsSettingsScreen />);
  let pending!: Promise<void>;
  await act(async () => { pending = mockSwitches["settings.push_notifications"].onValueChange(true); });
  mockSession++;
  await act(async () => { permission.resolve(true); await pending; });
  expect(registerRemotePushToken).not.toHaveBeenCalled();
  expect(mockUpdate).not.toHaveBeenCalled();
});

it("rejects settings callbacks retained from a previous focus visit", async () => {
  const ui = await render(<NotificationsSettingsScreen />);
  const toggle = mockSwitches["settings.push_notifications"].onValueChange;
  mockFocused = false; await ui.rerender(<NotificationsSettingsScreen />);
  mockFocused = true; await ui.rerender(<NotificationsSettingsScreen />);
  await act(async () => { await toggle(false); });
  expect(mockUpdate).not.toHaveBeenCalled();
  expect(unregisterRemotePushToken).not.toHaveBeenCalled();
});

it("keeps a pending settings mutation locked when the screen remounts", async () => {
  const saving = deferred<void>();
  mockUpdate.mockReturnValueOnce(saving.promise);
  const first = await render(<NotificationsSettingsScreen />);
  let pending!: Promise<void>;
  await act(async () => { pending = mockSwitches["settings.push_notifications"].onValueChange(false); });
  await first.unmount();
  await render(<NotificationsSettingsScreen />);
  expect(mockSwitches["settings.push_notifications"].disabled).toBe(true);
  await act(async () => { await mockSwitches["settings.push_notifications"].onValueChange(true); });
  expect(mockUpdate).toHaveBeenCalledTimes(1);
  await act(async () => { saving.resolve(); await pending; });
  expect(mockSwitches["settings.push_notifications"].disabled).toBe(false);
});

it.each([false, true])("finishes disabling after unmount only in the same account (account changed: %s)", async (accountChanged) => {
  const saving = deferred<void>();
  mockUpdate.mockReturnValueOnce(saving.promise);
  const ui = await render(<NotificationsSettingsScreen />);
  let pending!: Promise<void>;
  await act(async () => { pending = mockSwitches["settings.push_notifications"].onValueChange(false); });
  await ui.unmount();
  if (accountChanged) mockSession++;
  await act(async () => { saving.resolve(); await pending; });
  expect(mockUpdate).toHaveBeenCalledWith({ push_notifications_enabled: false });
  expect(unregisterRemotePushToken).toHaveBeenCalledTimes(accountChanged ? 0 : 1);
});

it.each([false, true])("finishes enabling after registration while offscreen only in the same account (account changed: %s)", async (accountChanged) => {
  const registration = deferred<void>();
  jest.mocked(registerRemotePushToken).mockReturnValueOnce(registration.promise);
  const ui = await render(<NotificationsSettingsScreen />);
  let pending!: Promise<void>;
  await act(async () => { pending = mockSwitches["settings.push_notifications"].onValueChange(true); });
  expect(registerRemotePushToken).toHaveBeenCalledTimes(1);
  await ui.unmount();
  if (accountChanged) mockSession++;
  await act(async () => { registration.resolve(); await pending; });
  expect(mockUpdate).toHaveBeenCalledTimes(accountChanged ? 0 : 1);
  if (!accountChanged) expect(mockUpdate).toHaveBeenCalledWith({ push_notifications_enabled: true });
});

it.each([false, true])("shows a delayed permission denial only in its current view (unmounted: %s)", async (unmounted) => {
  const permission = deferred<boolean>();
  jest.mocked(ensureNotificationPermission).mockReturnValueOnce(permission.promise);
  const ui = await render(<NotificationsSettingsScreen />);
  let pending!: Promise<void>;
  await act(async () => { pending = mockSwitches["settings.push_notifications"].onValueChange(true); });
  if (unmounted) await ui.unmount();
  await act(async () => { permission.resolve(false); await pending; });
  expect(Alert.alert).toHaveBeenCalledTimes(unmounted ? 0 : 1);
  expect(registerRemotePushToken).not.toHaveBeenCalled();
  expect(mockUpdate).not.toHaveBeenCalled();
});
