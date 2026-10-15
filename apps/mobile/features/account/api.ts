import { fetchExportText, request } from "@/lib/api/client";
import type { AuthSession, User } from "@/lib/api/types";
import type { PaidPlanId, PlanCatalog } from "@/lib/plan";

export type SettingsProposalApplied = {
  field: string;
  value: string;
  label: string;
};

export type SettingsConfirmResult = {
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
  /** Every plan with what it includes and its numbers (prices come from the store). */
  listPlans: (token: string) => request<PlanCatalog>("/billing/plans", token),
  exportData: (token: string) => request<unknown>("/auth/me/export", token),
  exportDataText: (token: string) => fetchExportText(token),
  deleteAccount: (token: string) =>
    request<void>("/auth/me", token, { method: "DELETE" }, true, 120_000),
  listSessions: (token: string) =>
    request<{ sessions: AuthSession[] }>("/auth/sessions", token),
  revokeSession: (token: string, sessionId: string) =>
    request<void>(`/auth/sessions/${encodeURIComponent(sessionId)}`, token, {
      method: "DELETE",
    }),
  logoutAll: (token: string) =>
    request<void>("/auth/logout-all", token, { method: "POST" }),
};
