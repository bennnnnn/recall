import * as SecureStore from 'expo-secure-store';

const TOKEN_KEY = 'recall_access_token';

// In-memory fallback when SecureStore native module isn't available (Expo Go)
let _mem: string | null = null;

export async function getToken(): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(TOKEN_KEY);
  } catch {
    return _mem;
  }
}

export async function setToken(token: string): Promise<void> {
  _mem = token;
  try {
    await SecureStore.setItemAsync(TOKEN_KEY, token);
  } catch {
    // persisted in _mem only
  }
}

export async function clearToken(): Promise<void> {
  _mem = null;
  try {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
  } catch {
    // nothing to clear in native store
  }
}
