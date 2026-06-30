import { getApiUrl } from "@/lib/config";
import type { SearchSource } from "@/lib/searchSources";

export type { SearchSource };

// Registered by AuthContext so an expired/invalid token (401) signs the user out.
let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(fn: (() => void) | null): void {
  onUnauthorized = fn;
}

export type User = {
  id: string;
  email: string;
  name: string | null;
  avatar_url: string | null;
  default_model: string;
  plan: "free" | "pro";
  enabled_models: string[] | null;
  response_style: string;
  response_tone: string;
  memory_enabled: boolean;
  push_notifications_enabled: boolean;
  reminder_lead_minutes: number;
  locale: string;
  timezone: string;
  location: string | null;
  created_at: string;
};

export type Chat = {
  id: string;
  title: string | null;
  model: string;
  pinned: boolean;
  archived?: boolean;
  project_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type Feedback = "up" | "down" | null;

export type MessagePage = {
  messages: Message[];
  has_more: boolean;
};

export type Message = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  model: string | null;
  feedback?: Feedback;
  recalled?: number;
  memory_hints?: string[];
  context_summarized?: number;
  search_sources?: SearchSource[];
  local_image_uri?: string | null;
  created_at: string;
};

export type Memory = {
  id: string;
  type: string;
  text: string;
  confidence: number | null;
  created_at: string;
  updated_at: string;
};

export type Todo = {
  id: string;
  content: string;
  topic: string;
  checked: boolean;
  due_at: string | null;
  sort_order: number | null;
  chat_id: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectKind = "general" | "language" | "vocabulary" | "programming" | "learning" | "math";
export type LanguageLevel = "level1" | "level2" | "level3" | "level4" | "level5" | "level6";
export type VocabStatus = "new" | "learning" | "mastered";
export type PartOfSpeech =
  | "noun"
  | "verb"
  | "adjective"
  | "adverb"
  | "pronoun"
  | "preposition"
  | "conjunction"
  | "interjection"
  | "phrase"
  | "other";

export type Project = {
  id: string;
  title: string;
  description: string | null;
  kind: ProjectKind;
  target_language: string;
  native_language: string | null;
  level: LanguageLevel;
  archived: boolean;
  created_at: string;
  updated_at: string;
};

export type ProjectItem = {
  id: string;
  list_title: string;
  content: string;
  note: string | null;
  part_of_speech: PartOfSpeech | string | null;
  definition: string | null;
  example_sentence: string | null;
  status: VocabStatus;
  mastered: boolean;
  mastered_at: string | null;
  last_reviewed_at: string | null;
  review_count: number;
  pronunciation_url: string | null;
  created_at: string;
};

export type ProjectStats = {
  total: number;
  new_count: number;
  learning_count: number;
  mastered_count: number;
  added_this_week: number;
  due_for_review: number;
};

export type ProjectListGroup = {
  list_title: string;
  items: ProjectItem[];
};

export type ProjectPosGroup = {
  part_of_speech: string;
  items: ProjectItem[];
};

export type ProjectPosGroupSummary = {
  part_of_speech: string;
  count: number;
  new_count: number;
  learning_count: number;
  mastered_count: number;
};

export type ProjectDetail = Project & {
  mastered_count: number;
  total_count: number;
  stats: ProjectStats;
  lists: ProjectListGroup[];
  by_part_of_speech: ProjectPosGroup[];
  pos_groups: ProjectPosGroupSummary[];
  decks: ProjectDeckSummary[];
};

export type SearchResult = {
  match_type: "message" | "title";
  message_id: string | null;
  chat_id: string;
  chat_title: string | null;
  content: string;
  role: string;
  created_at: string;
};

export type Template = {
  id: string;
  title: string;
  content: string;
  category: string;
  is_builtin: boolean;
  created_at: string;
  updated_at: string;
};

export type Suggestion = {
  id: string;
  text: string;
  category: string;
  source: string;
  created_at: string;
};

export type HomeUrgentTodo = {
  id: string;
  content: string;
  topic: string;
  due_at: string;
  minutes_until: number;
};

export type HomeStarter = {
  text: string;
  prompt: string;
  kind: "time" | "memory" | "chat" | "general" | "todo" | "project";
};

export type HomeProjectHighlight = {
  project_id: string;
  title: string;
};

export type HomeScreen = {
  greeting: string;
  subtitle: string | null;
  project_highlight: HomeProjectHighlight | null;
  urgent_todos: HomeUrgentTodo[];
  starters: HomeStarter[];
};

export type ChatList = {
  pinned: Chat[];
  today: Chat[];
  yesterday: Chat[];
  earlier: Chat[];
  archived: Chat[];
};

export type ProjectDeckSummary = {
  title: string;
  count: number;
  due_count: number;
  mastered_count: number;
};

export type Usage = {
  date: string;
  input_tokens: number;
  output_tokens: number;
  daily_limit: number;
  used_tokens?: number;
  remaining: number;
};

export type ModelInfo = {
  id: string;
  label: string;
  provider: string;
  description: string;
  tier: string;
  plan_access: "free" | "pro";
  available: boolean;
  input_price_per_m: number | null;
  output_price_per_m: number | null;
};

export type GoogleCalendarStatus = {
  connected: boolean;
  email?: string | null;
  configured: boolean;
  can_write?: boolean;
};

export type GoogleCalendarEvent = {
  id: string;
  title: string;
  start_at: string;
  end_at?: string | null;
  location?: string | null;
  all_day: boolean;
  calendar_name?: string | null;
};

export type GoogleGmailStatus = {
  connected: boolean;
  email?: string | null;
  configured: boolean;
  last_sync_at?: string | null;
};

export type SuggestedReminder = {
  id: string;
  title: string;
  due_at: string | null;
  notes: string | null;
  confidence: number;
  source_snippet: string | null;
  status: string;
  created_at: string;
  gmail_message_id: string;
};

export type AuthResult = { access_token: string; user: User };

function apiUrl(path: string) {
  return `${getApiUrl()}${path}`;
}

async function request<T>(
  path: string,
  token: string,
  init?: RequestInit,
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30_000);

  try {
    const response = await fetch(apiUrl(path), {
      ...init,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...(init?.headers ?? {}),
      },
    });

    if (!response.ok) {
      if (response.status === 401) {
        onUnauthorized?.();
      }
      const text = await response.text();
      throw new Error(text || `Request failed: ${response.status}`);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json() as Promise<T>;
  } finally {
    clearTimeout(timeout);
  }
}

export async function loginWithGoogle(idToken: string): Promise<AuthResult> {
  const response = await fetch(apiUrl("/auth/google"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken }),
  });
  if (!response.ok) {
    throw new Error("Google login failed");
  }
  return response.json() as Promise<AuthResult>;
}

export async function loginWithDev(
  email = "dev@recall.local",
  name = "Dev User",
): Promise<AuthResult> {
  const response = await fetch(apiUrl("/auth/dev"), {
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
  deleteAccount: (token: string) =>
    request<void>("/auth/me", token, { method: "DELETE" }),
  createChat: (token: string, model = "auto", projectId?: string) =>
    request<Chat>("/chats", token, {
      method: "POST",
      body: JSON.stringify({ model, ...(projectId ? { project_id: projectId } : {}) }),
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
  getProject: (token: string, id: string) => request<ProjectDetail>(`/projects/${id}`, token),

  getProjectPosItems: (
    token: string,
    projectId: string,
    partOfSpeech: string,
    options?: { limit?: number; offset?: number },
  ) => {
    const limit = options?.limit ?? 50;
    const offset = options?.offset ?? 0;
    return request<ProjectItem[]>(
      `/projects/${projectId}/pos/${encodeURIComponent(partOfSpeech)}/items?limit=${limit}&offset=${offset}`,
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
        "title" | "description" | "kind" | "archived" | "level" | "target_language" | "native_language"
      >
    >,
  ) =>
    request<Project>(`/projects/${id}`, token, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  addProjectDeckItem: (
    token: string,
    projectId: string,
    deckTitle: string,
    body: { content: string; definition?: string; example_sentence?: string },
  ) =>
    request<ProjectItem>(
      `/projects/${projectId}/decks/${encodeURIComponent(deckTitle)}/items`,
      token,
      { method: "POST", body: JSON.stringify(body) },
    ),
  deleteProject: (token: string, id: string) =>
    request<void>(`/projects/${id}`, token, { method: "DELETE" }),
  search: (token: string, q: string, limit = 20) =>
    request<{ results: SearchResult[]; total: number }>(
      `/search?q=${encodeURIComponent(q)}&limit=${limit}`,
      token,
    ),
  listTemplates: (token: string) => request<Template[]>("/templates", token),
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
    request<{ events: GoogleCalendarEvent[] }>(
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
  syncGoogleGmail: (token: string) =>
    request<{
      status: string;
      message_count: number;
      reminders_created: number;
      skipped?: boolean;
    }>("/integrations/google-gmail/sync", token, { method: "POST" }),
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
