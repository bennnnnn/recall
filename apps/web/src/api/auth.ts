import { apiUrl, fetchWithTimeout, setTokenPair } from "@/api/client";
import type { AuthResult } from "@/api/types";

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
  const result = (await response.json()) as AuthResult;
  setTokenPair(result.access_token, result.refresh_token);
  return result;
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
  const result = (await response.json()) as AuthResult;
  setTokenPair(result.access_token, result.refresh_token);
  return result;
}

export async function logoutSession(
  token: string,
  refreshToken: string | null,
): Promise<void> {
  try {
    await fetch(apiUrl("/auth/logout"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch {
    /* best-effort */
  }
}
