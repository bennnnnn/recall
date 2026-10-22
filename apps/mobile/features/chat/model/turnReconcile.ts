import type { Message } from "@/lib/api";
import { MESSAGE_PAGE_SIZE } from "@/features/chat/model/constants";
import { mergeLocalAttachmentUris } from "@/features/chat/model/messageMerge";

/**
 * A turn the server took (it sent `start`) keeps running when the connection
 * drops: the server finishes and saves it, and a deploy saves what it had. The
 * phone reloads the chat until that reply lands instead of offering a second
 * send of the same message.
 */
export const DROPPED_TURN_POLL_MS = 2_000;
/**
 * Each wait is spread by this much either way: a deploy closes every socket at
 * once, and phones that polled on the same beat would arrive together.
 */
const POLL_JITTER = 0.25;
/** The longest one wait can be. */
export const DROPPED_TURN_MAX_WAIT_MS = DROPPED_TURN_POLL_MS * (1 + POLL_JITTER);
/**
 * Rows a poll reads: the dropped turn and the exchange before it. The full page is
 * read once, when the reply has landed (code-health audit NET-14).
 */
export const DROPPED_TURN_PROBE_ROWS = 4;
/** A dropped socket: the server is still writing the reply. */
export const DROPPED_TURN_POLLS = 15;
/** A dropped SSE stream: the server stopped the turn and saved what it had at once. */
export const SSE_DROPPED_TURN_POLLS = 3;

const SERVER_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** answered: the reply is saved. saved: the message is, its reply not yet. missing: neither. */
type DroppedTurnState = "answered" | "saved" | "missing";

export type DroppedTurnResult = {
  /** "unknown" when no reload succeeded. */
  state: DroppedTurnState | "unknown";
  page: Message[] | null;
};

/** The server rows the phone shows already: everything from before the dropped turn. */
export function knownServerIds(messages: Message[]): Set<string> {
  return new Set(messages.filter((message) => SERVER_ID.test(message.id)).map((m) => m.id));
}

/** Where the dropped turn stands in the chat's newest page. */
export function droppedTurnState(page: Message[], known: ReadonlySet<string>): DroppedTurnState {
  const userIndex = page.findLastIndex((m) => m.role === "user" && !known.has(m.id));
  if (userIndex < 0) return "missing";
  const isNewReply = (m: Message) => m.role === "assistant" && !known.has(m.id);
  return page.slice(userIndex + 1).some(isNewReply) ? "answered" : "saved";
}

/** The newest page in place of the turn's local bubbles; older pages already loaded stay. */
export function mergeReconciledPage(previous: Message[], page: Message[]): Message[] {
  const pageIds = new Set(page.map((message) => message.id));
  const firstShared = previous.findIndex((message) => pageIds.has(message.id));
  const older = firstShared > 0 ? previous.slice(0, firstShared) : [];
  return [...older, ...mergeLocalAttachmentUris(previous, page)];
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** One poll's wait, somewhere in `DROPPED_TURN_POLL_MS` ± 25%. */
export function droppedTurnWaitMs(random: () => number = Math.random): number {
  return Math.round(DROPPED_TURN_POLL_MS * (1 - POLL_JITTER + 2 * POLL_JITTER * random()));
}

/**
 * Reload until the turn is answered or the polls run out; null once
 * `stillWaiting` says the wait was abandoned (Stop, a new turn, another chat).
 * A poll reads the newest few rows; the answered turn is settled with a full
 * page, which reaches the rows the phone still shows under local ids.
 */
export async function pollDroppedTurn({
  fetchPage,
  known,
  stillWaiting,
  polls = DROPPED_TURN_POLLS,
  wait = sleep,
  random = Math.random,
}: {
  fetchPage: (limit: number) => Promise<Message[]>;
  known: ReadonlySet<string>;
  stillWaiting: () => boolean;
  polls?: number;
  wait?: (ms: number) => Promise<void>;
  random?: () => number;
}): Promise<DroppedTurnResult | null> {
  let last: DroppedTurnResult = { state: "unknown", page: null };
  for (let poll = 0; poll < polls; poll += 1) {
    await wait(droppedTurnWaitMs(random));
    if (!stillWaiting()) return null;
    try {
      const probe = await fetchPage(DROPPED_TURN_PROBE_ROWS);
      if (!stillWaiting()) return null;
      const state = droppedTurnState(probe, known);
      if (state === "answered") {
        const page = await fetchPage(MESSAGE_PAGE_SIZE);
        if (!stillWaiting()) return null;
        return { state, page };
      }
      last = { state, page: null };
    } catch {
      // The network that dropped the socket may be coming back; poll again.
    }
  }
  return last;
}
