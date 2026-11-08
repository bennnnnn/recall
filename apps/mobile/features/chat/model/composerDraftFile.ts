import { cacheFile } from "@/lib/cache/cacheFile";
import { parseJsonRecord } from "@/lib/jsonFence";

/**
 * The composer's unsent text for each chat (and New Chat), kept on disk for this
 * account: drafts lived only in memory and were gone when the phone closed the
 * app in the background.
 */
const draftsFile = cacheFile("recall-composer-drafts.json");

/** Drafts kept; the least recently written goes first. */
const MAX_DRAFTS = 50;

/** Tagged with the account that typed them, so another account's file is never used. */
type Stored = { user_id: string; drafts: Record<string, string> };

/** This account's drafts by thread key; empty when there is none, it is unreadable or another account wrote it. */
export async function readComposerDrafts(owner: string): Promise<Map<string, string>> {
  const drafts = new Map<string, string>();
  const raw = await draftsFile.read();
  const stored = raw === null ? null : parseJsonRecord(raw);
  const saved = stored?.user_id === owner ? stored.drafts : null;
  if (typeof saved !== "object" || saved === null) return drafts;
  for (const [key, text] of Object.entries(saved)) {
    if (typeof text === "string" && text.trim()) drafts.set(key, text);
  }
  return drafts;
}

/** Keep `drafts` (the newest last) for `owner`; with none left, the file goes. */
export function writeComposerDrafts(owner: string, drafts: Map<string, string>): Promise<void> {
  const kept = [...drafts].filter(([, text]) => text.trim()).slice(-MAX_DRAFTS);
  if (kept.length === 0) return draftsFile.clear();
  const stored: Stored = { user_id: owner, drafts: Object.fromEntries(kept) };
  return draftsFile.write(JSON.stringify(stored));
}

/** Sign-out. */
export function clearSavedComposerDrafts(): Promise<void> {
  return draftsFile.clear();
}
