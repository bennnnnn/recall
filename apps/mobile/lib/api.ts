import { getApiUrl } from "@/lib/config";
import { getDeviceTimezone } from "@/lib/deviceTimezone";
import { readRecordingBase64, speechUploadFromUri } from "@/lib/voiceAudio";

import {
  apiUrl,
  fetchExportText,
  fetchWithTimeout,
  request,
} from "@/lib/api/client";

export type * from "@/lib/api/types";
export {
  logoutSession,
  setTokenRefreshHandler,
  setUnauthorizedHandler,
} from "@/lib/api/client";

import type {
  AuthResult,
  Chat,
  ChatList,
  Feedback,
  GoogleCalendarEvent,
  GoogleCalendarStatus,
  GoogleGmailStatus,
  HomeScreen,
  LanguageLevel,
  Memory,
  Message,
  MessagePage,
  ModelInfo,
  Project,
  ProjectDetail,
  ProjectItem,
  ProjectKind,
  SearchResult,
  SuggestedReminder,
  Suggestion,
  Todo,
  Usage,
  User,
  VocabStatus,
} from "@/lib/api/types";

export async function loginWithGoogle(idToken: string): Promise<AuthResult> {
  const response = await fetchWithTimeout(apiUrl("/auth/google"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken }),
  });
  if (!response.ok) {
    throw new Error("Google login failed");
  }
  return response.json() as Promise<AuthResult>;
}

export async function loginWithApple(
  idToken: string,
  name?: string | null,
): Promise<AuthResult> {
  const response = await fetchWithTimeout(apiUrl("/auth/apple"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken, name: name ?? null }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Apple login failed");
  }
  return response.json() as Promise<AuthResult>;
}

export async function loginWithDev(
  email = "dev@recall.local",
  name = "Dev User",
): Promise<AuthResult> {
  const response = await fetchWithTimeout(apiUrl("/auth/dev"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, name }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Dev login failed — is the API running?");
  }
  return response.json() as Promise<AuthResult>;
}

export async function transcribeSpeech(
  token: string,
  fileUri: string,
): Promise<string> {
  const upload = speechUploadFromUri(fileUri);
  const audioBase64 = await readRecordingBase64(fileUri);
  if (!audioBase64) {
    throw new Error("recording_empty");
  }
  const response = await fetchWithTimeout(apiUrl("/speech/transcribe"), {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      audio_base64: audioBase64,
      filename: upload.name,
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "transcribe_failed");
  }
  const data = (await response.json()) as { text?: string };
  const text = (data.text ?? "").trim();
  if (!text) throw new Error("transcribe_empty");
  return text;
}

function normalizeMessagePage(data: MessagePage | Message[]): MessagePage {
  if (Array.isArray(data)) {
    return { messages: data, has_more: false };
  }
  return data;
}

export const api = {
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
  createChat: (
    token: string,
    model = "auto",
    projectId?: string,
    quizMode?: "exam" | "chat",
  ) =>
    request<Chat>("/chats", token, {
      method: "POST",
      body: JSON.stringify({
        model,
        ...(projectId ? { project_id: projectId } : {}),
        ...(quizMode ? { quiz_mode: quizMode } : {}),
      }),
    }),
  getChat: (token: string, chatId: string) =>
    request<Chat>(`/chats/${chatId}`, token),
  renameChat: (token: string, chatId: string, title: string) =>
    request<Chat>(`/chats/${chatId}`, token, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),
  setPin: (token: string, chatId: string, pinned: boolean) =>
    request<Chat>(`/chats/${chatId}/pin`, token, {
      method: "PATCH",
      body: JSON.stringify({ pinned }),
    }),
  setArchive: (token: string, chatId: string, archived: boolean) =>
    request<Chat>(`/chats/${chatId}/archive`, token, {
      method: "PATCH",
      body: JSON.stringify({ archived }),
    }),
  deleteChat: (token: string, chatId: string) =>
    request<void>(`/chats/${chatId}`, token, { method: "DELETE" }),
  deleteChatIfEmpty: async (token: string, chatId: string) => {
    const page = normalizeMessagePage(
      await request<MessagePage | Message[]>(
        `/chats/${chatId}/messages?limit=20`,
        token,
      ),
    );
    const hasAssistant = page.messages.some((m) => m.role === "assistant");
    if (page.messages.length === 0 || !hasAssistant) {
      await request<void>(`/chats/${chatId}`, token, { method: "DELETE" });
    }
  },
  listChats: (token: string) => request<ChatList>("/chats", token),
  listMessages: async (
    token: string,
    chatId: string,
    opts?: { limit?: number; before?: string },
  ) => {
    const params = new URLSearchParams();
    if (opts?.limit != null) params.set("limit", String(opts.limit));
    if (opts?.before) params.set("before", opts.before);
    const qs = params.toString();
    const data = await request<MessagePage | Message[]>(
      `/chats/${chatId}/messages${qs ? `?${qs}` : ""}`,
      token,
    );
    return normalizeMessagePage(data);
  },
  listAllMessages: async (
    token: string,
    chatId: string,
  ): Promise<Message[]> => {
    const batch = 100;
    let before: string | undefined;
    let hasMore = true;
    let all: Message[] = [];
    while (hasMore) {
      const page = await api.listMessages(token, chatId, {
        limit: batch,
        before,
      });
      if (!before) {
        all = page.messages;
      } else {
        all = [...page.messages, ...all];
      }
      hasMore = page.has_more;
      if (hasMore && page.messages.length > 0) {
        before = page.messages[0].id;
      } else {
        break;
      }
    }
    return all;
  },
  setMessageFeedback: (
    token: string,
    chatId: string,
    messageId: string,
    feedback: Feedback,
  ) =>
    request<Message>(`/chats/${chatId}/messages/${messageId}/feedback`, token, {
      method: "PATCH",
      body: JSON.stringify({ feedback }),
    }),
  listMemories: (token: string) => request<Memory[]>("/memories", token),
  deleteMemorySection: (token: string, type: string) =>
    request<void>(`/memories/type/${type}`, token, { method: "DELETE" }),
  deleteMemoryFact: (token: string, memoryId: string, factIndex: number) =>
    request<void>(`/memories/${memoryId}/facts/${factIndex}`, token, {
      method: "DELETE",
    }),
  todayUsage: (token: string) => request<Usage>("/chats/usage/today", token),
  listModels: (token: string) => request<ModelInfo[]>("/models", token),
  listTodos: (token: string) => request<Todo[]>("/todos", token),
  listTodoTopics: (token: string) => request<string[]>("/todos/topics", token),
  createTodo: (
    token: string,
    content: string,
    topic = "General",
    options?: { chatId?: string; dueAt?: string | null },
  ) =>
    request<Todo>("/todos", token, {
      method: "POST",
      body: JSON.stringify({
        content,
        topic,
        chat_id: options?.chatId ?? null,
        due_at: options?.dueAt ?? undefined,
      }),
    }),
  updateTodo: (
    token: string,
    id: string,
    patch: Partial<Pick<Todo, "content" | "topic" | "checked" | "due_at" | "sort_order">>,
  ) =>
    request<Todo>(`/todos/${id}`, token, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  reorderTodos: (
    token: string,
    items: { id: string; sort_order: number; topic?: string }[],
  ) =>
    request<Todo[]>("/todos/reorder", token, {
      method: "POST",
      body: JSON.stringify({ items }),
    }),
  deleteTodo: (token: string, id: string) =>
    request<void>(`/todos/${id}`, token, { method: "DELETE" }),
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
  search: (token: string, q: string, limit = 20, init?: Pick<RequestInit, "signal">) =>
    request<{ results: SearchResult[]; total: number }>(
      `/search?q=${encodeURIComponent(q)}&limit=${limit}`,
      token,
      init,
    ),
  listSuggestions: (token: string) => request<Suggestion[]>("/suggestions", token),

  getHomeScreen: (token: string, clientTimezone?: string) => {
    const params = clientTimezone
      ? `?client_timezone=${encodeURIComponent(clientTimezone)}`
      : "";
    return request<HomeScreen>(`/home${params}`, token);
  },
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
  dismissSuggestion: (token: string, id: string) =>
    request<void>(`/suggestions/${id}/dismiss`, token, { method: "POST" }),
  registerPushToken: (
    token: string,
    body: { expo_push_token: string; platform: string; device_id?: string },
  ) =>
    request<void>("/users/push-token", token, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  presignAttachment: (
    token: string,
    body: { content_type: string; size_bytes: number },
  ) =>
    request<{
      attachment_id: string;
      upload_url: string;
      storage_key: string;
      headers: Record<string, string>;
      api_upload: boolean;
    }>("/attachments/presign", token, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  cancelAttachment: (token: string, attachmentId: string) =>
    request<void>(`/attachments/${attachmentId}`, token, {
      method: "DELETE",
    }),
  confirmAttachment: (token: string, attachmentId: string) =>
    request<void>(`/attachments/${attachmentId}/confirm`, token, {
      method: "POST",
    }),
  getAttachmentUrl: (token: string, attachmentId: string) =>
    request<{
      id: string;
      content_type: string;
      size_bytes: number;
      download_url: string;
      created_at: string;
    }>(`/attachments/${attachmentId}/url`, token),
};

export function chatWebSocketUrl(chatId: string) {
  const base = getApiUrl().replace(/^http/, "ws");
  return `${base}/ws/chats/${chatId}`;
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(apiUrl("/health"));
    return res.ok;
  } catch {
    return false;
  }
}
