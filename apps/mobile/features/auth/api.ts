/** Sign-in with Google, Apple, or dev auth, and the consent asked right after it.
 * Session refresh lives in lib/api/client.ts. */
import { apiUrl, fetchWithTimeout, request } from "@/lib/api/client";
import type { AuthResult, User } from "@/lib/api/types";
import { deviceSessionFields } from "@/lib/deviceSession";

export async function loginWithGoogle(idToken: string): Promise<AuthResult> {
  const response = await fetchWithTimeout(apiUrl("/auth/google"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken, ...deviceSessionFields() }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Google login failed");
  }
  return response.json() as Promise<AuthResult>;
}

export async function loginWithApple(
  idToken: string,
  name: string | null,
  nonce: string,
): Promise<AuthResult> {
  const response = await fetchWithTimeout(apiUrl("/auth/apple"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      id_token: idToken,
      name: name ?? null,
      nonce,
      ...deviceSessionFields(),
    }),
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
    body: JSON.stringify({ email, name, ...deviceSessionFields() }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Dev login failed — is the API running?");
  }
  return response.json() as Promise<AuthResult>;
}

/** Record that the user agreed to the outside-AI disclosure; the server stamps the time. */
export function agreeToAiDataSharing(token: string): Promise<User> {
  return request<User>("/auth/me", token, {
    method: "PATCH",
    body: JSON.stringify({ ai_data_consent: true }),
  });
}
