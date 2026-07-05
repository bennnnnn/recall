import { fetchExportText, request } from "@/lib/api/client";
import type { User } from "@/lib/api/types";

export const accountApi = {
  me: (token: string) => request<User>("/auth/me", token),
  updateMe: (token: string, body: Partial<User>) =>
    request<User>("/auth/me", token, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  devUpgradePro: (token: string) =>
    request<User>("/auth/me/pro-dev", token, { method: "POST" }),
  syncSubscription: (token: string) =>
    request<User>("/auth/me/sync-subscription", token, { method: "POST" }),
  exportData: (token: string) => request<unknown>("/auth/me/export", token),
  exportDataText: (token: string) => fetchExportText(token),
  deleteAccount: (token: string) =>
    request<void>("/auth/me", token, { method: "DELETE" }),
};
