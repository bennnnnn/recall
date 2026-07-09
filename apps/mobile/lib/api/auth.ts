import { readRecordingBase64, speechUploadFromUri } from "@/lib/voiceAudio";

import { apiUrl, fetchWithTimeout } from "@/lib/api/client";
import type { AuthResult } from "@/lib/api/types";

export async function loginWithGoogle(idToken: string): Promise<AuthResult> {
  const response = await fetchWithTimeout(apiUrl("/auth/google"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Google login failed");
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
  name = "Bini",
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

export async function transcribeSpeech(token: string, fileUri: string): Promise<string> {
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
