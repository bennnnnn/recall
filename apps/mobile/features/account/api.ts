import { fetchExportText, request, requestRevalidated } from "@/lib/api/client";
import type { AuthSession, User } from "@/lib/api/types";
import type { PaidPlanId } from "@/lib/plan";

/** What a delete says to mean it (apps/api models/schemas/auth.py ACCOUNT_DELETE_CONFIRMATION). */
export const ACCOUNT_DELETE_CONFIRMATION = "delete";

type SettingsProposalApplied = {
  field: string;
  value: string;
  label: string;
};

type SettingsConfirmResult = {
  user: User;
  appearance: string | null;
  applied: SettingsProposalApplied[];
};

export const accountApi = {
  me: (token: string) => request<User>("/auth/me", token),
  updateMe: (token: string, body: Partial<User>) =>
    request<User>("/auth/me", token, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  confirmSettingsProposal: (token: string, proposalId: string) =>
    request<SettingsConfirmResult>(
      `/auth/me/settings-proposals/${proposalId}/confirm`,
      token,
      { method: "POST" },
    ),
  devUpgradePro: (token: string, plan: PaidPlanId = "pro") =>
    request<User>(`/auth/me/pro-dev?plan=${plan}`, token, { method: "POST" }),
  syncSubscription: (token: string) =>
    request<User>("/auth/me/sync-subscription", token, { method: "POST" }),
  exportDataText: (token: string, signal?: AbortSignal) => fetchExportText(token, true, signal),
  /**
   * Called only after the user confirmed it, and says so: the server deletes nothing without
   * `confirm` (apps/api account/api.py delete_me). With a fresh Sign in with Apple code, the
   * server also revokes the Apple grant.
   */
  deleteAccount: (token: string, appleAuthorizationCode?: string | null) =>
    request<void>(
      "/auth/me",
      token,
      {
        method: "DELETE",
        body: JSON.stringify({
          confirm: ACCOUNT_DELETE_CONFIRMATION,
          ...(appleAuthorizationCode ? { apple_authorization_code: appleAuthorizationCode } : {}),
        }),
      },
      true,
      120_000,
    ),
  /** Read on each Security visit; an unchanged list is a 304 by its ETag. */
  listSessions: (token: string) =>
    requestRevalidated<{ sessions: AuthSession[] }>("/auth/sessions", token),
  revokeSession: (token: string, sessionId: string) =>
    request<void>(`/auth/sessions/${encodeURIComponent(sessionId)}`, token, {
      method: "DELETE",
    }),
  logoutAll: (token: string) =>
    request<void>("/auth/logout-all", token, { method: "POST" }),
};
