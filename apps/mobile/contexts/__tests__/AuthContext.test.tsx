import React, { useLayoutEffect } from "react";
import { Text } from "react-native";
import { act, fireEvent, render } from "@testing-library/react-native";

import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { api, loginWithDev, logoutSession, setTokenRefreshHandler, type User } from "@/lib/api";
import { getToken, setTokenPair } from "@/lib/auth";
import { readCachedUser, writeCachedUser } from "@/lib/cachedUser";

jest.mock("@/lib/api", () => ({
  api: { me: jest.fn(), updateMe: jest.fn() },
  loginWithGoogle: jest.fn(), loginWithApple: jest.fn(), loginWithDev: jest.fn(),
  logoutSession: jest.fn(), setTokenRefreshHandler: jest.fn(), setUnauthorizedHandler: jest.fn(),
}));
jest.mock("@/lib/auth", () => {
  let generation = 0;
  return {
    getSessionGeneration: () => generation,
    invalidateSession: () => ++generation,
    getToken: jest.fn(), getRefreshToken: jest.fn(async () => "refresh-a"),
    setTokenPair: jest.fn(async () => true),
    clearToken: jest.fn(async () => { generation++; }),
    getOnboarded: jest.fn(async () => true), setOnboarded: jest.fn(), clearOnboarded: jest.fn(),
  };
});
jest.mock("@/lib/cachedUser", () => ({
  cachedUserMatchesToken: jest.fn(() => true),
  readCachedUser: jest.fn(), writeCachedUser: jest.fn(), clearCachedUser: jest.fn(),
  mergeCachedUser: (value: User) => value,
}));
jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
jest.mock("@/lib/theme", () => ({ useTheme: () => ({ bg: "white", primary: "blue" }) }));
jest.mock("@/lib/i18n", () => ({ ensureLocale: jest.fn() }));
jest.mock("@/hooks/useBootstrapSync", () => ({ useBootstrapSync: jest.fn() }));
jest.mock("@/lib/apple-auth", () => ({ signInWithAppleCredentials: jest.fn() }));
jest.mock("@/lib/google-auth", () => ({ signInWithGoogleIdToken: jest.fn(), signOutGoogle: jest.fn() }));
jest.mock("@/lib/signOutCleanup", () => ({ clearSignedOutAccount: jest.fn() }));

const userA = { id: "account-a", name: "Alice", locale: "en" } as User;
const userB = { id: "account-b", name: "Bob", locale: "en" } as User;
let current: ReturnType<typeof useAuth>;

function Probe() {
  const auth = useAuth();
  useLayoutEffect(() => { current = auth; }, [auth]);
  return <Text>{auth.user?.name ?? "signed-out"}</Text>;
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

async function mount() {
  return render(<AuthProvider><Probe /></AuthProvider>);
}

beforeEach(() => {
  jest.clearAllMocks();
  (getToken as jest.Mock).mockResolvedValue("access-a");
  (readCachedUser as jest.Mock).mockResolvedValue(userA);
  (api.me as jest.Mock).mockResolvedValue(userA);
  (logoutSession as jest.Mock).mockResolvedValue(undefined);
  (loginWithDev as jest.Mock).mockResolvedValue({ access_token: "access-b", refresh_token: "refresh-b", user: userB });
});

it("clears the visible account before a slow logout request finishes", async () => {
  const logout = deferred<void>();
  (logoutSession as jest.Mock).mockReturnValue(logout.promise);
  await mount();
  let pending!: Promise<void>;
  await act(async () => { pending = current.signOut(); });
  expect(current.user).toBeNull();
  expect(current.token).toBeNull();
  await act(async () => { logout.resolve(); await pending; });
});

it("does not restore an account or its cache when startup validation finishes after signout", async () => {
  const me = deferred<User>();
  (api.me as jest.Mock).mockReturnValue(me.promise);
  await mount();
  await act(async () => { await current.signOut(); });
  (writeCachedUser as jest.Mock).mockClear();
  await act(async () => { me.resolve(userA); });
  expect(current.user).toBeNull();
  expect(writeCachedUser).not.toHaveBeenCalled();
});

it("keeps the refreshed access token when uncached startup validation succeeds", async () => {
  (readCachedUser as jest.Mock).mockResolvedValue(null);
  (api.me as jest.Mock).mockImplementation(async () => {
    (getToken as jest.Mock).mockResolvedValue("access-refreshed");
    const callback = (setTokenRefreshHandler as jest.Mock).mock.calls.at(-1)[0];
    callback("access-refreshed", userA);
    return userA;
  });
  await mount();
  expect(current.user?.id).toBe(userA.id);
  expect(current.token).toBe("access-refreshed");
});

it("ignores a profile refresh belonging to a previous account", async () => {
  await mount();
  const me = deferred<User>();
  (api.me as jest.Mock).mockReturnValue(me.promise);
  let pending!: Promise<void>;
  await act(async () => { pending = current.refreshUser(); });
  await act(async () => { await current.signOut(); await current.signInWithDev(); });
  (writeCachedUser as jest.Mock).mockClear();
  await act(async () => { me.resolve(userA); await pending; });
  expect(current.user?.id).toBe(userB.id);
  expect(writeCachedUser).not.toHaveBeenCalled();
});

it("does not roll back a new account when the previous account's profile update fails", async () => {
  await mount();
  const update = deferred<User>();
  (api.updateMe as jest.Mock).mockReturnValue(update.promise);
  let pending!: Promise<void>;
  await act(async () => { pending = current.updateUser({ name: "Changed" }).catch(() => {}); });
  await act(async () => { await current.signOut(); await current.signInWithDev(); });
  await act(async () => { update.reject(new Error("offline")); await pending; });
  expect(current.user?.id).toBe(userB.id);
});

it("keeps the latest sign-in when an older sign-in completes last", async () => {
  await mount();
  const older = deferred<{ access_token: string; refresh_token: string; user: User }>();
  (loginWithDev as jest.Mock).mockReturnValueOnce(older.promise);
  let pending!: Promise<void>;
  await act(async () => { pending = current.signInWithDev(); });
  await act(async () => { await current.signInWithDev(); });
  (setTokenPair as jest.Mock).mockClear();
  await act(async () => {
    older.resolve({ access_token: "access-old", refresh_token: "refresh-old", user: userA });
    await pending;
  });
  expect(current.user?.id).toBe(userB.id);
  expect(setTokenPair).not.toHaveBeenCalled();
});

it("does not persist credentials from a sign-in cancelled by signout", async () => {
  await mount();
  const login = deferred<{ access_token: string; refresh_token: string; user: User }>();
  (loginWithDev as jest.Mock).mockReturnValue(login.promise);
  let pending!: Promise<void>;
  await act(async () => { pending = current.signInWithDev(); });
  await act(async () => { await current.signOut(); });
  await act(async () => {
    login.resolve({ access_token: "access-b", refresh_token: "refresh-b", user: userB });
    await pending;
  });
  expect(current.user).toBeNull();
  expect(setTokenPair).not.toHaveBeenCalled();
});

it("does not let a retained merge callback change the next account", async () => {
  await mount();
  const mergePreviousUser = current.mergeUser;
  await act(async () => { await current.signOut(); await current.signInWithDev(); });
  await act(async () => { mergePreviousUser({ name: "Alice's delayed update" }); });
  expect(current.user?.name).toBe("Bob");
});

it("does not bootstrap account preferences from cached display defaults", async () => {
  const me = deferred<User>();
  (api.me as jest.Mock).mockReturnValue(me.promise);
  await mount();
  const { useBootstrapSync } = jest.requireMock("@/hooks/useBootstrapSync");
  expect(current.user?.id).toBe(userA.id);
  expect(useBootstrapSync.mock.calls.at(-1)[0]).toEqual(expect.objectContaining({ token: null, user: null }));
  await act(async () => { me.resolve(userA); });
  expect(useBootstrapSync.mock.calls.at(-1)[0]).toEqual(expect.objectContaining({ token: "access-a", user: userA }));
});

it("retries secure credential loading without treating a storage failure as logout", async () => {
  (getToken as jest.Mock).mockRejectedValueOnce(new Error("keychain unavailable"));
  const rendered = await mount();
  expect(rendered.getByText("login.error_generic")).toBeTruthy();
  expect(rendered.queryByText("signed-out")).toBeNull();
  await fireEvent.press(rendered.getByRole("button", { name: "common.retry" }));
  expect(current.user?.id).toBe(userA.id);
});

it("retries offline startup without a cached user", async () => {
  (readCachedUser as jest.Mock).mockResolvedValue(null);
  (api.me as jest.Mock).mockRejectedValueOnce(new Error("offline"));
  const rendered = await mount();
  expect(rendered.getByText("login.error_generic")).toBeTruthy();
  expect(rendered.queryByText("signed-out")).toBeNull();
  await fireEvent.press(rendered.getByRole("button", { name: "common.retry" }));
  expect(current.user?.id).toBe(userA.id);
});

it("signs out when startup validation reports a genuine unauthorized session", async () => {
  (readCachedUser as jest.Mock).mockResolvedValue(null);
  (api.me as jest.Mock).mockImplementation(async () => {
    const { setUnauthorizedHandler } = jest.requireMock("@/lib/api");
    setUnauthorizedHandler.mock.calls.at(-1)[0]();
    throw new Error("unauthorized");
  });
  const rendered = await mount();
  expect(rendered.getByText("signed-out")).toBeTruthy();
  expect(rendered.queryByText("login.error_generic")).toBeNull();
});

it("does not authenticate credentials returned by a dismissed native login", async () => {
  const native = deferred<string>();
  const { signInWithGoogleIdToken } = jest.requireMock("@/lib/google-auth");
  const { loginWithGoogle } = jest.requireMock("@/lib/api");
  signInWithGoogleIdToken.mockReturnValue(native.promise);
  await mount();
  let pending!: Promise<void>;
  await act(async () => { pending = current.signInWithGoogle(); });
  await act(async () => { await current.signOut(); });
  await act(async () => { native.resolve("id-token"); await pending; });
  expect(loginWithGoogle).not.toHaveBeenCalled();
});

it("waits for local account cleanup before another login, without waiting for backend logout", async () => {
  const cleanup = deferred<void>();
  const logout = deferred<void>();
  const { clearSignedOutAccount } = jest.requireMock("@/lib/signOutCleanup");
  clearSignedOutAccount.mockReturnValueOnce(cleanup.promise);
  (logoutSession as jest.Mock).mockReturnValueOnce(logout.promise);
  await mount();
  let signingOut!: Promise<void>;
  let signingIn!: Promise<void>;
  await act(async () => {
    signingOut = current.signOut();
    signingIn = current.signInWithDev();
  });
  expect(current.user).toBeNull();
  expect(loginWithDev).not.toHaveBeenCalled();
  await act(async () => { cleanup.resolve(); await signingOut; await signingIn; });
  expect(current.user?.id).toBe(userB.id);
  await act(async () => { logout.resolve(); });
  expect(current.user?.id).toBe(userB.id);
});

it("never paints another account's cached profile while validating stored credentials", async () => {
  const me = deferred<User>();
  const { cachedUserMatchesToken } = jest.requireMock("@/lib/cachedUser");
  cachedUserMatchesToken.mockReturnValueOnce(false);
  (api.me as jest.Mock).mockReturnValue(me.promise);
  const rendered = await mount();
  expect(rendered.queryByText("Alice")).toBeNull();
  await act(async () => { me.resolve(userB); });
  expect(current.user?.id).toBe(userB.id);
});

it("preserves matching cached first paint during a temporary startup outage", async () => {
  (api.me as jest.Mock).mockRejectedValue(new Error("offline"));
  const rendered = await mount();
  expect(rendered.getByText("Alice")).toBeTruthy();
  expect(current.token).toBe("access-a");
  expect(rendered.queryByText("login.error_generic")).toBeNull();
});
