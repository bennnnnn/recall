import { forgetPadMathDrafts, isPadMathDraft, notePadMathDraft } from "@/features/chat/model/padMathDrafts";
import { cacheFile } from "@/lib/cache/cacheFile";
import { parseJsonRecord } from "@/lib/fence/json";

/**
 * The composer's unsent text for each chat (and New Chat), kept on disk for this
 * account: drafts lived only in memory and were gone when the phone closed the
 * app in the background.
 */
const draftsFile = cacheFile("recall-composer-drafts.json");

/** Drafts kept; the least recently written goes first. */
const MAX_DRAFTS = 50;
/** The most of one draft kept on disk (a pasted book is not a draft to bring back whole). */
const MAX_DRAFT_CHARS = 20_000;

/** `text` cut to the cap, on a character, never inside one. */
function capped(text: string): string {
  return text.length <= MAX_DRAFT_CHARS ? text : Array.from(text).slice(0, MAX_DRAFT_CHARS).join("");
}

/** Tagged with the account that typed them, so another account's file is never used. `math`
 * names the drafts whose maths the math keyboard wrote. */
type Stored = { user_id: string; drafts: Record<string, string>; math?: string[] };

/** This account's drafts by thread key; empty when there is none, it is unreadable or another account wrote it. */
export async function readComposerDrafts(owner: string): Promise<Map<string, string>> {
  const drafts = new Map<string, string>();
  const raw = await draftsFile.read();
  const stored = raw === null ? null : parseJsonRecord(raw);
  const saved = stored?.user_id === owner ? stored.drafts : null;
  if (typeof saved !== "object" || saved === null) return drafts;
  const math = new Set(Array.isArray(stored?.math) ? stored.math : []);
  for (const [key, text] of Object.entries(saved)) {
    if (typeof text !== "string" || !text.trim()) continue;
    drafts.set(key, capped(text));
    if (math.has(key)) notePadMathDraft(capped(text));
  }
  return drafts;
}

/** Keep `drafts` (the least recently written first) for `owner`; with none left, the file goes. */
export function writeComposerDrafts(owner: string, drafts: Map<string, string>): Promise<void> {
  const kept = [...drafts].filter(([, text]) => text.trim()).slice(-MAX_DRAFTS)
    .map(([key, text]) => [key, capped(text)] as const);
  if (kept.length === 0) return draftsFile.clear();
  const math = kept.filter(([, text]) => isPadMathDraft(text)).map(([key]) => key);
  const stored: Stored = { user_id: owner, drafts: Object.fromEntries(kept), ...(math.length ? { math } : {}) };
  return draftsFile.write(JSON.stringify(stored));
}

/** Sign-out. */
export function clearSavedComposerDrafts(): Promise<void> {
  forgetPadMathDrafts();
  return draftsFile.clear();
}
