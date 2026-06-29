import { isExpoGo } from "@/lib/expoRuntime";
import { requestGoogleIntegrationAuthCode } from "@/lib/google-integration-auth";

const GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly";

const EXPO_GO_MESSAGE =
  "Gmail requires a dev build (pnpm expo run:ios). In Expo Go, connect is unavailable.";

/** Request Gmail read-only access — independent of Recall sign-in. */
export async function connectGoogleGmail(): Promise<string> {
  if (isExpoGo()) {
    throw new Error(EXPO_GO_MESSAGE);
  }

  return requestGoogleIntegrationAuthCode([GMAIL_SCOPE], {
    cancelledMessage: "Gmail connect cancelled",
    failedMessage: "Gmail connect failed.",
  });
}
