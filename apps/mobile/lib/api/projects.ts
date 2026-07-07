import { getDeviceTimezone } from "@/lib/deviceTimezone";

import { request } from "@/lib/api/client";
import type {
  LanguageLevel,
  Project,
  ProjectDailyQuiz,
  ProjectDetail,
  ProjectItem,
  ProjectKind,
  ProjectQuizAnswerResult,
  QuizModality,
  VocabStatus,
} from "@/lib/api/types";

export const projectsApi = {
  listProjects: (token: string) => request<Project[]>("/projects", token),
  getProject: (token: string, id: string) => {
    const tz = getDeviceTimezone();
    const qs = tz ? `?client_timezone=${encodeURIComponent(tz)}` : "";
    return request<ProjectDetail>(`/projects/${id}${qs}`, token);
  },

  getProjectDailyItems: (
    token: string,
    projectId: string,
    activityDate: string,
    options?: { limit?: number; offset?: number },
  ) => {
    const tz = getDeviceTimezone();
    const limit = options?.limit ?? 50;
    const offset = options?.offset ?? 0;
    const params = new URLSearchParams({
      activity_date: activityDate,
      limit: String(limit),
      offset: String(offset),
    });
    if (tz) params.set("client_timezone", tz);
    return request<ProjectItem[]>(
      `/projects/${projectId}/daily-items?${params.toString()}`,
      token,
    );
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
  updateProjectItem: (
    token: string,
    projectId: string,
    itemId: string,
    patch: { status?: VocabStatus; definition?: string | null },
  ) =>
    request<ProjectItem>(`/projects/${projectId}/items/${itemId}`, token, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  deleteProject: (token: string, id: string) =>
    request<void>(`/projects/${id}`, token, { method: "DELETE" }),
  recordProjectQuizAnswer: (
    token: string,
    projectId: string,
    body: {
      chat_id: string;
      assistant_message_id: string;
      letter: string;
      topic?: string;
      question?: string;
      is_correct?: boolean;
    },
  ) =>
    request<void>(`/projects/${projectId}/quiz-answer`, token, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  ensureDailyQuiz: (token: string, projectId: string) => {
    const tz = getDeviceTimezone();
    const qs = tz ? `?client_timezone=${encodeURIComponent(tz)}` : "";
    return request<ProjectDailyQuiz>(`/projects/${projectId}/quiz/daily/ensure${qs}`, token, {
      method: "POST",
    }, true, 120_000);
  },

  getDailyQuiz: (token: string, projectId: string) => {
    const tz = getDeviceTimezone();
    const qs = tz ? `?client_timezone=${encodeURIComponent(tz)}` : "";
    return request<ProjectDailyQuiz>(`/projects/${projectId}/quiz/daily${qs}`, token);
  },

  prefetchDailyQuiz: (token: string, projectId: string) => {
    const tz = getDeviceTimezone();
    const qs = tz ? `?client_timezone=${encodeURIComponent(tz)}` : "";
    return request<void>(`/projects/${projectId}/quiz/daily/prefetch${qs}`, token, {
      method: "POST",
    }, true, 120_000);
  },

  answerDailyQuiz: (
    token: string,
    projectId: string,
    questionId: string,
    body: {
      modality?: QuizModality;
      letter?: string;
      text?: string;
      chat_id?: string;
      skip?: boolean;
    },
  ) => {
    const tz = getDeviceTimezone();
    const qs = tz ? `?client_timezone=${encodeURIComponent(tz)}` : "";
    return request<ProjectQuizAnswerResult>(
      `/projects/${projectId}/quiz/daily/${questionId}/answer${qs}`,
      token,
      { method: "POST", body: JSON.stringify(body) },
    );
  },
};
