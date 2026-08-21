import { request } from "@/lib/api/client";

export type ProductEventName =
  | "paywall_viewed"
  | "purchase_started"
  | "purchase_succeeded"
  | "purchase_failed"
  | "push_permission";

export type ProductEventInput = {
  name: ProductEventName;
  properties: Record<string, string>;
  platform?: "ios" | "android" | "web";
  app_version?: string;
  installation_id?: string;
  client_at: string;
};

export const analyticsApi = {
  recordProductEvents: (token: string, events: ProductEventInput[]) =>
    request<void>("/analytics/events", token, {
      method: "POST",
      body: JSON.stringify({ events }),
    }),
};
