import { Platform } from "react-native";

import { isExpoGo } from "@/lib/expoRuntime";

export { isExpoGo } from "@/lib/expoRuntime";

type AppleAuthModule = typeof import("expo-apple-authentication");

let appleModule: AppleAuthModule | null | undefined;

async function loadAppleAuth(): Promise<AppleAuthModule> {
  if (appleModule) return appleModule;
  try {
    appleModule = await import("expo-apple-authentication");
    return appleModule;
  } catch {
    throw new Error(
      "Sign in with Apple native module is missing. Rebuild the dev client: cd apps/mobile && pnpm expo run:ios",
    );
  }
}

/** Sign in with Apple is iOS-only; never shown on Android. */
export function isAppleSignInPlatform(): boolean {
  return Platform.OS === "ios";
}

export async function isAppleSignInAvailable(): Promise<boolean> {
  if (!isAppleSignInPlatform()) return false;
  try {
    const mod = await loadAppleAuth();
    return await mod.isAvailableAsync();
  } catch {
    return false;
  }
}

/** Always show the Apple button on iOS; check availability when the user taps. */
export function shouldShowAppleSignInButton(): boolean {
  return isAppleSignInPlatform();
}

export type AppleSignInResult = {
  idToken: string;
  name: string | null;
};

export function formatAppleSignInError(error: unknown): string {
  const message =
    error instanceof Error ? error.message : typeof error === "string" ? error : "";
  if (/could not load bundle/i.test(message)) {
    return "bundle_load_failed";
  }
  if (/native module/i.test(message)) {
    return "native_module_missing";
  }
  if (/cancel/i.test(message)) {
    return "Sign-in cancelled";
  }
  return message || "generic";
}

export async function signInWithAppleCredentials(): Promise<AppleSignInResult> {
  if (!isAppleSignInPlatform()) {
    throw new Error("Sign in with Apple is only available on iOS.");
  }
  const AppleAuthentication = await loadAppleAuth();
  const available = await AppleAuthentication.isAvailableAsync();
  if (!available) {
    throw new Error(
      "Sign in with Apple is not available on this device. On the iOS Simulator, open Settings → Apple Account and sign in, then try again.",
    );
  }

  const credential = await AppleAuthentication.signInAsync({
    requestedScopes: [
      AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
      AppleAuthentication.AppleAuthenticationScope.EMAIL,
    ],
  });

  const idToken = credential.identityToken;
  if (!idToken) {
    throw new Error("Apple Sign-In did not return an identity token.");
  }

  const given = credential.fullName?.givenName?.trim();
  const family = credential.fullName?.familyName?.trim();
  const name = [given, family].filter(Boolean).join(" ") || null;

  return { idToken, name };
}
