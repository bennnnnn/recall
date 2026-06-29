import { isExpoGo } from "@/lib/expoRuntime";
import { requestGoogleIntegrationAuthCode } from "@/lib/google-integration-auth";

const CALENDAR_READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly";
const CALENDAR_WRITE_SCOPE = "https://www.googleapis.com/auth/calendar.events";

const EXPO_GO_MESSAGE =
  'Google Calendar requires a dev build (pnpm expo run:ios). In Expo Go, connect is unavailable.';

export async function connectGoogleCalendar(options?: { write?: boolean }): Promise<string> {
  if (isExpoGo()) {
    throw new Error(EXPO_GO_MESSAGE);
  }

  const scopes = options?.write
    ? [CALENDAR_READONLY_SCOPE, CALENDAR_WRITE_SCOPE]
    : [CALENDAR_READONLY_SCOPE];

  return requestGoogleIntegrationAuthCode(scopes, {
    cancelledMessage: "Calendar connect cancelled",
    failedMessage: "Google Calendar connect failed.",
  });
}
