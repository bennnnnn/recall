import { act, renderHook } from "@testing-library/react-native";
import { Alert, Platform } from "react-native";

import { useLoginActions } from "@/hooks/useLoginActions";
import { formatAppleSignInError } from "@/lib/apple-auth";
import {
  isGoogleSignInConfigured,
  isGoogleWebClientConfigured,
} from "@/lib/config";
import { formatGoogleSignInError, isExpoGo } from "@/lib/google-auth";

const mockApple = jest.fn();
const mockGoogle = jest.fn();
const mockDev = jest.fn();
const mockFeedback = { error: jest.fn() };

jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    signInWithApple: mockApple,
    signInWithGoogle: mockGoogle,
    signInWithDev: mockDev,
  }),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => mockFeedback,
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@/lib/haptics", () => ({ tap: jest.fn() }));
jest.mock("@/lib/apple-auth", () => ({
  formatAppleSignInError: jest.fn(),
}));
jest.mock("@/lib/google-auth", () => ({
  formatGoogleSignInError: jest.fn(),
  isExpoGo: jest.fn(),
}));
jest.mock("@/lib/config", () => ({
  isGoogleSignInConfigured: jest.fn(),
  isGoogleWebClientConfigured: jest.fn(),
}));

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

beforeEach(() => {
  jest.clearAllMocks();
  jest.replaceProperty(Platform, "OS", "ios");
  jest.mocked(isExpoGo).mockReturnValue(false);
  jest.mocked(isGoogleSignInConfigured).mockReturnValue(true);
  jest.mocked(isGoogleWebClientConfigured).mockReturnValue(true);
  jest.mocked(formatAppleSignInError).mockReturnValue("generic");
  jest.mocked(formatGoogleSignInError).mockReturnValue("generic");
  mockApple.mockResolvedValue(undefined);
  mockGoogle.mockResolvedValue(undefined);
  mockDev.mockResolvedValue(undefined);
});

afterEach(() => jest.restoreAllMocks());

it.each([
  ["apple", "handleApple", mockApple],
  ["google", "handleGoogle", mockGoogle],
  ["dev", "handleDev", mockDev],
] as const)("tracks only the active %s provider", async (provider, action, signIn) => {
  const pending = deferred();
  signIn.mockReturnValueOnce(pending.promise);
  const { result } = await renderHook(useLoginActions);

  let request!: Promise<void>;
  await act(async () => {
    request = result.current[action]();
    await Promise.resolve();
  });
  expect(result.current.busy).toBe(true);
  expect(result.current.busyProvider).toBe(provider);

  await act(async () => {
    pending.resolve();
    await request;
  });
  expect(result.current.busy).toBe(false);
  expect(result.current.busyProvider).toBeNull();
});

it.each([
  ["bundle_load_failed", "login.error_bundle"],
  ["native_module_missing", "login.error_native_module"],
  ["not_configured", "login.error_not_configured"],
  ["android_oauth_setup", "login.error_android_google"],
  ["generic", "login.error_generic"],
  ["provider detail", "provider detail"],
] as const)("maps Google error %s to %s", async (providerError, expected) => {
  jest.mocked(formatGoogleSignInError).mockReturnValue(providerError);
  mockGoogle.mockRejectedValueOnce(new Error("failed"));
  const { result } = await renderHook(useLoginActions);

  await act(async () => result.current.handleGoogle());

  expect(mockFeedback.error).toHaveBeenCalledWith(expected);
});

it("does not report a cancelled provider flow", async () => {
  jest.mocked(formatAppleSignInError).mockReturnValue("cancelled");
  mockApple.mockRejectedValueOnce(new Error("cancelled"));
  const { result } = await renderHook(useLoginActions);

  await act(async () => result.current.handleApple());

  expect(mockFeedback.error).not.toHaveBeenCalled();
});

it("keeps a second provider from starting while one is pending", async () => {
  const pending = deferred();
  mockApple.mockReturnValueOnce(pending.promise);
  const { result } = await renderHook(useLoginActions);

  let request!: Promise<void>;
  await act(async () => {
    request = result.current.handleApple();
    await result.current.handleGoogle();
  });
  expect(mockGoogle).not.toHaveBeenCalled();

  await act(async () => {
    pending.resolve();
    await request;
  });
});

it("preserves the Expo Go Google availability alert", async () => {
  jest.mocked(isExpoGo).mockReturnValue(true);
  jest.spyOn(Alert, "alert").mockImplementation(() => {});
  const { result } = await renderHook(useLoginActions);

  await act(async () => result.current.handleGoogle());

  expect(Alert.alert).toHaveBeenCalledWith(
    "login.google_unavailable_title",
    "login.google_unavailable_body",
  );
  expect(mockGoogle).not.toHaveBeenCalled();
});
