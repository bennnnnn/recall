import * as SecureStore from "expo-secure-store";

const KEY_PREFIX = "recall.list-group-order.";

function storageKey(userId: string): string {
  const safe = userId.replace(/[^a-zA-Z0-9._-]/g, "_");
  return `${KEY_PREFIX}${safe || "default"}`;
}

export async function loadListGroupOrder(userId: string): Promise<string[]> {
  try {
    const raw = await SecureStore.getItemAsync(storageKey(userId));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((value): value is string => typeof value === "string");
  } catch {
    return [];
  }
}

export async function saveListGroupOrder(userId: string, topics: string[]): Promise<void> {
  await SecureStore.setItemAsync(storageKey(userId), JSON.stringify(topics));
}
