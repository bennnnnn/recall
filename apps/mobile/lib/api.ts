import { getApiUrl } from '@/lib/config';

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
  created_at: string;
  updated_at: string;
};

export type Message = {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  model: string | null;
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

export type AuthResult = { access_token: string; user: User };

function apiUrl(path: string) {
  return `${getApiUrl()}${path}`;
}

async function request<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function loginWithGoogle(idToken: string): Promise<AuthResult> {
  const response = await fetch(apiUrl('/auth/google'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id_token: idToken }),
  });
  if (!response.ok) {
    throw new Error('Google login failed');
  }
  return response.json() as Promise<AuthResult>;
}

export async function loginWithDev(
  email = 'dev@recall.local',
  name = 'Dev User',
): Promise<AuthResult> {
  const response = await fetch(apiUrl('/auth/dev'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, name }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || 'Dev login failed — is the API running?');
  }
  return response.json() as Promise<AuthResult>;
}

export const api = {
  me: (token: string) => request<User>('/auth/me', token),
  updateMe: (token: string, body: Partial<User>) =>
    request<User>('/auth/me', token, { method: 'PATCH', body: JSON.stringify(body) }),
  createChat: (token: string, model = 'free-chat') =>
    request<Chat>('/chats', token, { method: 'POST', body: JSON.stringify({ model }) }),
  getChat: (token: string, chatId: string) => request<Chat>(`/chats/${chatId}`, token),
  renameChat: (token: string, chatId: string, title: string) =>
    request<Chat>(`/chats/${chatId}`, token, { method: 'PATCH', body: JSON.stringify({ title }) }),
  deleteChat: (token: string, chatId: string) =>
    request<void>(`/chats/${chatId}`, token, { method: 'DELETE' }),
  listChats: (token: string) => request<ChatList>('/chats', token),
  listMessages: (token: string, chatId: string) =>
    request<Message[]>(`/chats/${chatId}/messages`, token),
  listMemories: (token: string) => request<Memory[]>('/memories', token),
  deleteMemory: (token: string, memoryId: string) =>
    request<void>(`/memories/${memoryId}`, token, { method: 'DELETE' }),
  todayUsage: (token: string) => request<Usage>('/chats/usage/today', token),
};

export function chatWebSocketUrl(chatId: string) {
  const base = getApiUrl().replace(/^http/, 'ws');
  return `${base}/ws/chats/${chatId}`;
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(apiUrl('/health'));
    return res.ok;
  } catch {
    return false;
  }
}
