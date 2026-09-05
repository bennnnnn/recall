import { getDeviceTimezone } from "@/lib/deviceTimezone";

import { request } from "@/lib/api/client";
import type {
  LanguageLevel,
  Project,
  ProjectDetail,
  ProjectItem,
  ProjectKind,
} from "@/lib/api/types";

export const projectsApi = {
  listProjects: (token: string) => {
    const tz = getDeviceTimezone();
    const qs = tz ? `?client_timezone=${encodeURIComponent(tz)}` : "";
    return request<Project[]>(`/projects${qs}`, token);
  },
  getProject: (token: string, id: string, opts?: { includeLists?: boolean }) => {
    const tz = getDeviceTimezone();
    const params = new URLSearchParams();
    if (tz) params.set("client_timezone", tz);
    if (opts?.includeLists) params.set("include_lists", "true");
    const qs = params.toString();
    return request<ProjectDetail>(`/projects/${id}${qs ? `?${qs}` : ""}`, token);
  },

  getProjectDailyItems: (
    token: string,
    projectId: string,
    activityDate: string,
    options?: { limit?: number; offset?: number; bucket?: "mastered" | "missed" },
  ) => {
    const tz = getDeviceTimezone();
    const limit = options?.limit ?? 50;
    const offset = options?.offset ?? 0;
    const params = new URLSearchParams({
      activity_date: activityDate,
      limit: String(limit),
      offset: String(offset),
    });
    if (options?.bucket) params.set("bucket", options.bucket);
    if (tz) params.set("client_timezone", tz);
    return request<ProjectItem[]>(`/projects/${projectId}/daily-items?${params.toString()}`, token);
  },

  createProject: (
    token: string,
    body: {
      title: string;
      description?: string | null;
      kind?: ProjectKind;
      target_language?: string;
      native_language?: string | null;
      level?: LanguageLevel;
      daily_goal?: number | null;
    },
  ) =>
    request<Project>("/projects", token, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateProject: (
    token: string,
    id: string,
    patch: Partial<
      Pick<
        Project,
        | "title"
        | "description"
        | "kind"
        | "archived"
        | "level"
        | "target_language"
        | "native_language"
        | "daily_goal"
      >
    >,
  ) =>
    request<Project>(`/projects/${id}`, token, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  recordProjectPractice: (
    token: string,
    projectId: string,
    itemId: string,
    outcome: { attempt_id: string; was_correct: boolean; completes_word: boolean },
  ) =>
    request<{ item: ProjectItem; recorded: boolean; newly_mastered: boolean }>(
      `/projects/${projectId}/items/${itemId}/practice`,
      token,
      {
        method: "POST",
        body: JSON.stringify(outcome),
      },
    ),
};
