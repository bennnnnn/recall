import { config } from "@/lib/config";
import {
  isConsentCancelled,
  readServerAuthCode,
} from "@/lib/google-integration-auth-code";

/**
 * OAuth for integrations (Gmail, Calendar) — separate from Recall sign-in.
 * Sign-in uses id tokens only (`google-auth.ts`); integrations request scoped
 * server auth codes with offline access for refresh tokens on the backend.
 */
export async function requestGoogleIntegrationAuthCode(
  scopes: string[],
  options?: {
    cancelledMessage?: string;
    failedMessage?: string;
  },
): Promise<string> {
  const { GoogleSignin, statusCodes } =
    await import("@react-native-google-signin/google-signin");

  GoogleSignin.configure({
    webClientId: config.googleWebClientId,
    iosClientId: config.googleIosClientId,
    offlineAccess: true,
    // Android only. Without this, a second Google product (or write upgrade)
    // often reuses a consumed auth code and Google omits refresh_token.
    forceCodeForRefreshToken: true,
    scopes,
  });

  try {
    await GoogleSignin.hasPlayServices({ showPlayServicesUpdateDialog: true });
    const signedIn = await GoogleSignin.getCurrentUser();
    if (signedIn) {
      const added = await GoogleSignin.addScopes({ scopes });
      if (isConsentCancelled(added)) {
        throw new Error(options?.cancelledMessage ?? "Connect cancelled");
      }
      const fromConsent = readServerAuthCode(added);
      if (fromConsent) {
        return fromConsent;
      }
      // Do not use getCurrentUser().serverAuthCode — that is leftover from
      // Recall sign-in (already exchanged, or never issued).
    }
    const response = await GoogleSignin.signIn();
    if (isConsentCancelled(response)) {
      throw new Error(options?.cancelledMessage ?? "Connect cancelled");
    }
    const serverAuthCode = readServerAuthCode(response);
    if (!serverAuthCode) {
      throw new Error(
        "Google did not return an authorization code. Disconnect the integration, " +
          "revoke Recall in your Google account permissions, then connect again.",
      );
    }
    return serverAuthCode;
  } catch (error: unknown) {
    const err = error as { code?: string; message?: string };
    if (err.code === statusCodes.SIGN_IN_CANCELLED) {
      throw new Error(options?.cancelledMessage ?? "Connect cancelled");
    }
    throw new Error(err.message ?? options?.failedMessage ?? "Connect failed.");
  }
}
