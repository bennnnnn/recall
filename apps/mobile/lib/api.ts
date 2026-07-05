import { getApiUrl } from "@/lib/config";
import { readRecordingBase64, speechUploadFromUri } from "@/lib/voiceAudio";

import { accountApi } from "@/lib/api/account";
import { attachmentsApi } from "@/lib/api/attachments";
import { chatsApi } from "@/lib/api/chats";
import {
  apiUrl,
  fetchWithTimeout,
} from "@/lib/api/client";
import { discoverApi } from "@/lib/api/discover";
import { integrationsApi } from "@/lib/api/integrations";
import { memoriesApi } from "@/lib/api/memories";
import { projectsApi } from "@/lib/api/projects";
import { todosApi } from "@/lib/api/todos";

export type * from "@/lib/api/types";
export {
  logoutSession,
  setTokenRefreshHandler,
  setUnauthorizedHandler,
} from "@/lib/api/client";

import type { AuthResult } from "@/lib/api/types";

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

export const api = {
  ...accountApi,
  ...chatsApi,
  ...memoriesApi,
  ...discoverApi,
  ...todosApi,
  ...projectsApi,
  ...integrationsApi,
  ...attachmentsApi,
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
