import { getApiUrl } from "@/lib/config";

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
  response_style: string;
  memory_enabled: boolean;
};

export type Chat = {
  id: string;
  title: string | null;
  model: string;
  pinned: boolean;
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

export type ChatList = {
  pinned: Chat[];
  today: Chat[];
  yesterday: Chat[];
  earlier: Chat[];
};

export type Usage = {
  date: string;
  input_tokens: number;
  output_tokens: number;
  daily_limit: number;
  remaining: number;
};

export type ModelInfo = {
  id: string;
  label: string;
  provider: string;
  description: string;
  tier: string;
  available: boolean;
  input_price_per_m: number | null;
  output_price_per_m: number | null;
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
  const response = await fetch(apiUrl(path), {
    ...init,
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
  exportData: (token: string) => request<unknown>("/auth/me/export", token),
  deleteAccount: (token: string) =>
    request<void>("/auth/me", token, { method: "DELETE" }),
  createChat: (token: string, model = "free-chat") =>
    request<Chat>("/chats", token, {
      method: "POST",
      body: JSON.stringify({ model }),
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
  deleteChat: (token: string, chatId: string) =>
    request<void>(`/chats/${chatId}`, token, { method: "DELETE" }),
  deleteChatIfEmpty: async (token: string, chatId: string) => {
    const page = normalizeMessagePage(
      await request<MessagePage | Message[]>(
        `/chats/${chatId}/messages?limit=1`,
        token,
      ),
    );
    if (page.messages.length === 0) {
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
  deleteMemory: (token: string, memoryId: string) =>
    request<void>(`/memories/${memoryId}`, token, { method: "DELETE" }),
  todayUsage: (token: string) => request<Usage>("/chats/usage/today", token),
  listModels: (token: string) => request<ModelInfo[]>("/models", token),
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
