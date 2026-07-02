import * as SecureStore from "expo-secure-store";

const TOKEN_KEY = "recall_access_token";
const REFRESH_TOKEN_KEY = "recall_refresh_token";

// In-memory fallback when SecureStore native module isn't available (Expo Go)
let _memAccess: string | null = null;
let _memRefresh: string | null = null;

export async function getToken(): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(TOKEN_KEY);
  } catch {
    return _memAccess;
  }
}

export async function getRefreshToken(): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
  } catch {
    return _memRefresh;
  }
}

export async function setToken(token: string): Promise<void> {
  _memAccess = token;
  try {
    await SecureStore.setItemAsync(TOKEN_KEY, token);
  } catch {
    // persisted in _mem only
  }
}

export async function setRefreshToken(token: string): Promise<void> {
  _memRefresh = token;
  try {
    await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, token);
  } catch {
    // persisted in _mem only
  }
}

export async function setTokenPair(accessToken: string, refreshToken: string): Promise<void> {
  await Promise.all([setToken(accessToken), setRefreshToken(refreshToken)]);
}

export async function clearToken(): Promise<void> {
  _memAccess = null;
  _memRefresh = null;
  try {
    await Promise.all([
      SecureStore.deleteItemAsync(TOKEN_KEY),
      SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY),
    ]);
  } catch {
    // nothing to clear in native store
  }
}

const ONBOARDED_KEY = "recall_onboarded";
let _memOnboarded = false;

export async function getOnboarded(): Promise<boolean> {
  if (_memOnboarded) return true;
  try {
    return (await SecureStore.getItemAsync(ONBOARDED_KEY)) === "1";
  } catch {
    return _memOnboarded;
  }
}

export async function setOnboarded(): Promise<void> {
  _memOnboarded = true;
  try {
    await SecureStore.setItemAsync(ONBOARDED_KEY, "1");
  } catch {
    // persisted in memory only
  }
}
