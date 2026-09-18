import { request } from "@/lib/api/client";
import type { Automation, AutomationFrequency, AutomationStatus } from "@/lib/api/types";

export const automationsApi = {
  listAutomations: (token: string) => request<Automation[]>("/automations", token),
  getAutomation: (token: string, id: string) =>
    request<Automation>(`/automations/${id}`, token),
  createAutomation: (
    token: string,
    params: { prompt: string; frequency: AutomationFrequency; nextRunAt: string },
  ) =>
    request<Automation>("/automations", token, {
      method: "POST",
      body: JSON.stringify({
        prompt: params.prompt,
        frequency: params.frequency,
        next_run_at: params.nextRunAt,
      }),
    }),
  updateAutomation: (
    token: string,
    id: string,
    patch: Partial<{
      prompt: string;
      frequency: AutomationFrequency;
      next_run_at: string;
      status: Extract<AutomationStatus, "active" | "paused">;
    }>,
  ) =>
    request<Automation>(`/automations/${id}`, token, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  deleteAutomation: (token: string, id: string) =>
    request<void>(`/automations/${id}`, token, { method: "DELETE" }),
};
