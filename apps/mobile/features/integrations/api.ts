import { request } from "@/lib/api/client";
import type {
  GoogleCalendarEvent,
  GoogleCalendarStatus,
  GoogleGmailStatus,
  SuggestedReminder,
  Todo,
} from "@/lib/api/types";

export const integrationsApi = {
  googleCalendarStatus: (token: string) =>
    request<GoogleCalendarStatus>("/integrations/google-calendar/status", token),
  connectGoogleCalendar: (token: string, serverAuthCode: string) =>
    request<GoogleCalendarStatus>("/integrations/google-calendar/connect", token, {
      method: "POST",
      body: JSON.stringify({ server_auth_code: serverAuthCode }),
    }),
  disconnectGoogleCalendar: (token: string) =>
    request<void>("/integrations/google-calendar", token, { method: "DELETE" }),
  listGoogleCalendarEvents: (token: string) =>
    request<{ events: GoogleCalendarEvent[]; load_error?: string | null }>(
      "/integrations/google-calendar/events",
      token,
    ),
  proposeCalendarEvent: (
    token: string,
    body: {
      title: string;
      start_at: string;
      end_at: string;
      location?: string;
      description?: string;
    },
  ) =>
    request<{
      proposal_id: string;
      title: string;
      start_at: string;
      end_at: string;
      location?: string | null;
    }>("/integrations/google-calendar/events/propose", token, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  confirmCalendarEvent: (token: string, proposalId: string) =>
    request<GoogleCalendarEvent>(
      `/integrations/google-calendar/events/${proposalId}/confirm`,
      token,
      { method: "POST" },
    ),
  calendarConflicts: (token: string, dueAtIso: string) =>
    request<{
      conflicts: Array<{
        event_id: string;
        title: string;
        start_at: string;
        end_at?: string | null;
      }>;
    }>(`/integrations/google-calendar/conflicts?due_at=${encodeURIComponent(dueAtIso)}`, token),
  googleGmailStatus: (token: string) =>
    request<GoogleGmailStatus>("/integrations/google-gmail/status", token),
  connectGoogleGmail: (token: string, serverAuthCode: string) =>
    request<GoogleGmailStatus>("/integrations/google-gmail/connect", token, {
      method: "POST",
      body: JSON.stringify({ server_auth_code: serverAuthCode }),
    }),
  disconnectGoogleGmail: (token: string) =>
    request<void>("/integrations/google-gmail", token, { method: "DELETE" }),
  syncGoogleGmail: (token: string, options?: { force?: boolean }) =>
    request<{
      status: string;
      message_count: number;
      reminders_created: number;
      skipped?: boolean;
    }>(
      options?.force
        ? "/integrations/google-gmail/sync?force=true"
        : "/integrations/google-gmail/sync",
      token,
      { method: "POST" },
    ),
  listSuggestedReminders: (token: string) =>
    request<{ reminders: SuggestedReminder[]; pending_count: number }>(
      "/integrations/google-gmail/suggested-reminders",
      token,
    ),
  addSuggestedReminder: (token: string, id: string) =>
    request<Todo>(`/integrations/google-gmail/suggested-reminders/${id}/add`, token, {
      method: "POST",
    }),
  dismissSuggestedReminder: (token: string, id: string) =>
    request<void>(`/integrations/google-gmail/suggested-reminders/${id}/dismiss`, token, {
      method: "POST",
    }),
};
