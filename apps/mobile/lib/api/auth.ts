import { readRecordingBase64, speechUploadFromUri } from "@/lib/voiceAudio";
import i18n from "@/lib/i18n";

import { ApiRequestError, apiUrl, fetchWithTimeout, request } from "@/lib/api/client";
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
  name = "bini",
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

function speechLanguageHint(): string | undefined {
  const language = (i18n.resolvedLanguage || i18n.language || "").trim().toLowerCase();
  if (!language) return undefined;
  return language.split("-")[0] || undefined;
}

async function transcribeLegacy(
  token: string,
  audioBase64: string,
  filename: string,
): Promise<string> {
  const data = await request<{ text?: string }>(
    "/speech/transcribe",
    token,
    {
      method: "POST",
      body: JSON.stringify({ audio_base64: audioBase64, filename }),
    },
    true,
    60_000,
  );
  return (data.text ?? "").trim();
}

export async function transcribeSpeech(token: string, fileUri: string): Promise<string> {
  const upload = speechUploadFromUri(fileUri);
  const audioBase64 = await readRecordingBase64(fileUri);
  if (!audioBase64) {
    throw new Error("recording_empty");
  }
  try {
    let text = "";
    try {
      const data = await request<{ text?: string }>(
        "/speech/transcribe/v2",
        token,
        {
          method: "POST",
          body: JSON.stringify({
            audio_base64: audioBase64,
            filename: upload.name,
            language: speechLanguageHint(),
          }),
        },
        true,
        25_000,
      );
      text = (data.text ?? "").trim();
    } catch (error) {
      // Rollback path only: old builds/environments without OPENAI_API_KEY keep
      // dictation usable while Realtime voice is rolled out independently.
      if (!(error instanceof ApiRequestError) || ![404, 503].includes(error.status)) {
        throw error;
      }
      text = await transcribeLegacy(token, audioBase64, upload.name);
    }
    if (!text) throw new Error("transcribe_empty");
    return text;
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error("Transcription timed out. Check your connection.");
    }
    throw error;
  }
}