/** Sign-in with Google, Apple, or dev auth, and the consent asked right after it.
 * Session refresh lives in lib/api/client.ts. */
import {
  ApiRequestError,
  apiUrl,
  AUTH_FETCH_TIMEOUT_MS,
  fetchWithTimeout,
  request,
} from "@/lib/api/client";
import { serverUnreachableError, withDeadline } from "@/lib/api/deadline";
import type { AuthResult, User } from "@/lib/api/types";
import { AccountExistsError, accountExistsProvider } from "@/features/auth/model/accountExists";
import { SignInRefusedError, signInRefusalKey } from "@/features/auth/model/signInRefusal";
import { deviceSessionFields } from "@/lib/deviceSession";

/** A refused sign-in, read by its code: never the server's English (signInRefusal.ts). */
async function loginFailure(response: Response): Promise<Error> {
  const refused = new ApiRequestError(response.status, await response.text());
  const provider = accountExistsProvider(refused);
  if (provider) return new AccountExistsError(provider);
  return new SignInRefusedError(signInRefusalKey(refused));
}

/** One sign-in call and the reading of its reply, under one deadline: the headers'
 * timer alone left a stalled body spinning the sign-in button (code-health audit NET-17). */
function signIn(
  path: string,
  body: Record<string, unknown>,
  read: (response: Response) => Promise<AuthResult>,
): Promise<AuthResult> {
  return withDeadline(AUTH_FETCH_TIMEOUT_MS, null, async (signal) => read(
    await fetchWithTimeout(apiUrl(path), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    }),
  ), serverUnreachableError);
}

export function loginWithGoogle(idToken: string): Promise<AuthResult> {
  return signIn("/auth/google", { id_token: idToken, ...deviceSessionFields() }, async (response) => {
    if (!response.ok) throw await loginFailure(response);
    return (await response.json()) as AuthResult;
  });
}

export function loginWithApple(
  idToken: string,
  name: string | null,
  nonce: string,
): Promise<AuthResult> {
  const body = { id_token: idToken, name: name ?? null, nonce, ...deviceSessionFields() };
  return signIn("/auth/apple", body, async (response) => {
    if (!response.ok) throw await loginFailure(response);
    return (await response.json()) as AuthResult;
  });
}

export function loginWithDev(
  email = "dev@recall.local",
  name = "bini",
): Promise<AuthResult> {
  return signIn("/auth/dev", { email, name, ...deviceSessionFields() }, async (response) => {
    if (!response.ok) throw await loginFailure(response);
    return (await response.json()) as AuthResult;
  });
}

/** Record that the user agreed to the outside-AI disclosure; the server stamps the time. */
export function agreeToAiDataSharing(token: string): Promise<User> {
  return setAiDataSharing(token, true);
}

/** Withdraw that agreement: chat, voice and photo reads stop until the user agrees again. */
export function withdrawAiDataSharing(token: string): Promise<User> {
  return setAiDataSharing(token, false);
}

function setAiDataSharing(token: string, agreed: boolean): Promise<User> {
  return request<User>("/auth/me", token, {
    method: "PATCH",
    body: JSON.stringify({ ai_data_consent: agreed }),
  });
}
