import { config } from "@/lib/config";

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
    scopes,
  });

  try {
    await GoogleSignin.hasPlayServices({ showPlayServicesUpdateDialog: true });
    const signedIn = await GoogleSignin.getCurrentUser();
    let serverAuthCode: string | null | undefined;

    if (signedIn) {
      const added = await GoogleSignin.addScopes({ scopes });
      serverAuthCode = added?.data?.serverAuthCode ?? signedIn.serverAuthCode;
      if (!serverAuthCode) {
        const refreshed = await GoogleSignin.signInSilently();
        serverAuthCode = refreshed.data?.serverAuthCode;
      }
    } else {
      const response = await GoogleSignin.signIn();
      serverAuthCode = response.data?.serverAuthCode;
    }

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
