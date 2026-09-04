import React from "react";
import { Text } from "react-native";
import { act, render } from "@testing-library/react-native";

import { useBootstrapSync } from "@/hooks/useBootstrapSync";
import { api, type User } from "@/lib/api";
import { getDeviceLocationLabel } from "@/lib/deviceLocation";
import { registerPlanChangeListener } from "@/lib/purchases";

jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => 0 }));
jest.mock("@/lib/api", () => ({ api: { updateMe: jest.fn(), syncSubscription: jest.fn() } }));
jest.mock("@/lib/deviceTimezone", () => ({ getDeviceTimezone: () => "America/Los_Angeles" }));
jest.mock("@/lib/deviceLocation", () => ({ getDeviceLocationLabel: jest.fn() }));
jest.mock("@/lib/gmailAutoSync", () => ({ attachGmailForegroundSync: jest.fn() }));
jest.mock("@/lib/pushNotifications", () => ({ attachPushForegroundSync: jest.fn() }));
jest.mock("@/lib/reminderPrefs", () => ({ syncReminderLeadFromServer: jest.fn() }));
jest.mock("@/lib/purchases", () => ({
  configurePurchases: jest.fn(), isPurchasesConfigured: () => true,
  registerPlanChangeListener: jest.fn(),
}));

const userA = { id: "a", timezone: "UTC", location_enabled: false } as User;
const userB = { id: "b", timezone: "America/Los_Angeles", location_enabled: false } as User;
const setUser = jest.fn();

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((yes) => { resolve = yes; });
  return { promise, resolve };
}

function Probe({ user, token }: { user: User | null; token: string | null }) {
  useBootstrapSync({ user, token, setUser });
  return <Text>{user?.id ?? "out"}</Text>;
}

beforeEach(() => {
  jest.clearAllMocks();
  (api.updateMe as jest.Mock).mockResolvedValue(userA);
  (getDeviceLocationLabel as jest.Mock).mockResolvedValue(null);
  (registerPlanChangeListener as jest.Mock).mockResolvedValue(jest.fn());
});

it("does not restore a user when timezone sync returns after signout", async () => {
  const update = deferred<User>();
  (api.updateMe as jest.Mock).mockReturnValue(update.promise);
  const rendered = await render(<Probe user={userA} token="a" />);
  await rendered.rerender(<Probe user={null} token={null} />);
  await act(async () => { update.resolve({ ...userA, timezone: "America/Los_Angeles" }); });
  expect(setUser).not.toHaveBeenCalled();
});

it("does not send a stale location lookup after switching accounts", async () => {
  const location = deferred<string | null>();
  (getDeviceLocationLabel as jest.Mock).mockReturnValue(location.promise);
  const rendered = await render(<Probe user={{ ...userA, timezone: userB.timezone, location_enabled: true }} token="a" />);
  await rendered.rerender(<Probe user={userB} token="b" />);
  await act(async () => { location.resolve("San Francisco"); });
  expect(api.updateMe).not.toHaveBeenCalled();
});

it("ignores the old account's subscription response and detached listener", async () => {
  const subscription = deferred<User>();
  (api.syncSubscription as jest.Mock).mockReturnValue(subscription.promise);
  const rendered = await render(<Probe user={{ ...userA, timezone: userB.timezone }} token="a" />);
  const previousListener = (registerPlanChangeListener as jest.Mock).mock.calls[0][0];
  await act(async () => { previousListener(true); });
  await rendered.rerender(<Probe user={userB} token="b" />);
  await act(async () => { subscription.resolve({ ...userA, plan: "pro" }); previousListener(false); });
  expect(setUser).not.toHaveBeenCalled();
  expect(api.syncSubscription).toHaveBeenCalledTimes(1);
});

it("merges only the synced timezone into the current account", async () => {
  (api.updateMe as jest.Mock).mockResolvedValue({ ...userA, name: "Old name", timezone: userB.timezone });
  await render(<Probe user={userA} token="a" />);
  const applyUpdate = setUser.mock.calls[0][0];
  expect(applyUpdate({ ...userA, name: "New name" })).toEqual({ ...userA, name: "New name", timezone: userB.timezone });
  expect(applyUpdate(userB)).toEqual(userB);
  expect(applyUpdate(null)).toBeNull();
});
