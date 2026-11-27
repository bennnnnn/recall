/**
 * Until /auth/me answers, the phone acts on the settings the account last had, not on
 * placeholders (H3, 2026-11-27): a send named Auto instead of the chosen model, memory read as
 * off and a Pro user heard the phone's voice. The real launch cache, over an in-memory file.
 */
import React, { useLayoutEffect } from "react";
import { Text } from "react-native";
import { act, render } from "@testing-library/react-native";

import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { ModelsProvider } from "@/contexts/ModelsContext";
import { useChatComposerState } from "@/features/chat/hooks/useChatComposerState";
import { useModels } from "@/hooks/useModels";
import { api, type User } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { writeCachedUser } from "@/lib/cachedUser";
import { hasPlanFeature } from "@/lib/plan";

const mockFiles = new Map<string, string>();
jest.mock("@/lib/cache/cacheFile", () => ({
  cacheFile: (name: string) => ({
    read: async () => mockFiles.get(name) ?? null,
    readSync: () => mockFiles.get(name) ?? null,
    write: async (contents: string) => { mockFiles.set(name, contents); },
    clear: async () => { mockFiles.delete(name); },
  }),
}));
jest.mock("@/lib/api", () => ({
  api: { me: jest.fn(), updateMe: jest.fn(), listModels: jest.fn(async () => []) },
  loginWithGoogle: jest.fn(), loginWithApple: jest.fn(), loginWithDev: jest.fn(),
  logoutSession: jest.fn(), setTokenRefreshHandler: jest.fn(), setUnauthorizedHandler: jest.fn(),
  setConsentRequiredHandler: jest.fn(),
}));
jest.mock("@/lib/api/client", () => ({
  accessTokenNeedsRefresh: () => false,
  freshAccessToken: async (token: string) => token,
  refreshedAccount: () => null,
}));
jest.mock("@/lib/auth", () => ({
  getSessionGeneration: () => 0,
  invalidateSession: () => 1,
  getToken: jest.fn(), getRefreshToken: jest.fn(async () => "refresh-a"),
  setTokenPair: jest.fn(async () => true),
  clearToken: jest.fn(async () => undefined),
  getOnboarded: jest.fn(async () => true), setOnboarded: jest.fn(), clearOnboarded: jest.fn(),
  CorruptSessionError: class CorruptSessionError extends Error {},
}));
jest.mock("@/lib/cachedModels", () => ({ readCachedModels: jest.fn(async () => null), writeCachedModels: jest.fn() }));
jest.mock("@/lib/theme", () => ({ useTheme: () => ({ bg: "white", primary: "blue" }) }));
jest.mock("@/lib/i18n", () => ({ ensureLocale: jest.fn() }));
jest.mock("@/hooks/useBootstrapSync", () => ({ useBootstrapSync: jest.fn() }));
jest.mock("@/lib/apple-auth", () => ({ signInWithAppleCredentials: jest.fn() }));
jest.mock("@/lib/google-auth", () => ({ signInWithGoogleIdToken: jest.fn(), signOutGoogle: jest.fn() }));
jest.mock("@/lib/signOutCleanup", () => ({ clearSignedOutAccount: jest.fn() }));
jest.mock("@/lib/sentry", () => ({ reportCorruptSessionCleared: jest.fn() }));
jest.mock("@/lib/syncRecords", () => ({ forgetSyncRecords: jest.fn(async () => undefined) }));
jest.mock("@/lib/images/imageCaches", () => ({ clearImageCaches: jest.fn(async () => undefined) }));
jest.mock("@/lib/pendingLogout", () => ({ endServerSession: jest.fn(async () => undefined), watchPendingLogouts: jest.fn(() => () => {}) }));

function tokenFor(sub: string): string {
  const encode = (value: unknown) => btoa(JSON.stringify(value)).replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
  return `${encode({ alg: "HS256", typ: "JWT" })}.${encode({ sub })}.signature`;
}

/** A Pro account with Auto off and one model chosen, memory on and a voice picked. */
const proUser = {
  id: "account-a", email: "a@example.com", name: "Alice", avatar_url: null, locale: "en",
  plan: "pro", default_model: "smart-chat", enabled_models: ["smart-chat"],
  memory_enabled: true, emoji_use: "off", response_tone: "warm", tts_voice: "verse",
  push_notifications_enabled: true, reminder_lead_minutes: 10, timezone: "UTC",
  location: "Lyon", location_enabled: true, custom_instructions: "Be brief", age: 30,
  country: "FR", job: "Nurse", created_at: "2026-01-01T00:00:00Z",
} as unknown as User;

let shown: { user: User | null; validated: boolean; model: string };
function Probe() {
  const { user, profileValidated } = useAuth();
  const { autoEnabled, modelEnabledSet, AUTO_MODEL_ID } = useModels();
  const { selectedModel } = useChatComposerState({ autoEnabled, modelEnabledSet, autoModelId: AUTO_MODEL_ID });
  useLayoutEffect(() => { shown = { user, validated: profileValidated, model: selectedModel }; });
  return <Text>{user?.name ?? "signed-out"}</Text>;
}

beforeEach(() => {
  jest.clearAllMocks();
  mockFiles.clear();
  (getToken as jest.Mock).mockResolvedValue(tokenFor("account-a"));
  // /auth/me has not answered (a slow network, or offline).
  (api.me as jest.Mock).mockReturnValue(new Promise<User>(() => {}));
});

it("a send before /auth/me names the account's chosen model, and the plan and memory are its own", async () => {
  await writeCachedUser(proUser);
  await render(<AuthProvider><ModelsProvider><Probe /></ModelsProvider></AuthProvider>);
  await act(async () => {});

  expect(shown.validated).toBe(false);
  expect(shown.user?.name).toBe("Alice");
  expect(shown.model).toBe("smart-chat");
  expect(shown.user?.plan).toBe("pro");
  expect(hasPlanFeature(shown.user, "speech_tts")).toBe(true);
  expect(shown.user?.memory_enabled).toBe(true);
  expect(shown.user?.tts_voice).toBe("verse");
  expect(shown.user?.emoji_use).toBe("off");
});

it("keeps nothing personal in the launch cache", async () => {
  await writeCachedUser(proUser);
  const written = JSON.parse(mockFiles.get("cached-user.json") ?? "{}") as Record<string, unknown>;
  for (const field of ["email", "location", "location_enabled", "custom_instructions", "age", "country", "job",
    "push_notifications_enabled", "reminder_lead_minutes", "timezone"]) {
    expect(written).not.toHaveProperty(field);
  }
});

it("a cache from before the settings were kept is not painted: the launch waits for /auth/me", async () => {
  mockFiles.set("cached-user.json", JSON.stringify({ id: "account-a", name: "Alice", avatar_url: null, plan: "pro", locale: "en" }));
  const me: { resolve?: (user: User) => void } = {};
  (api.me as jest.Mock).mockReturnValue(new Promise<User>((resolve) => { me.resolve = resolve; }));
  const ui = await render(<AuthProvider><ModelsProvider><Probe /></ModelsProvider></AuthProvider>);
  await act(async () => {});
  expect(ui.queryByText("Alice")).toBeNull();

  await act(async () => { me.resolve?.(proUser); });
  expect(shown.validated).toBe(true);
  expect(shown.model).toBe("smart-chat");
});
