import { queueComposerAttachment } from "@/features/attachments/model/pendingComposerAttachment";
import { COMPOSER_NEW_THREAD_KEY } from "@/features/chat/model/composerThreadDraft";
import type { PendingSend } from "@/features/chat/model/sendLogic";

/** The longest a turn waits for the opened chat's page; then it goes out anyway. */
export const OPENED_PAGE_WAIT_MS = 4_000;

/** The composer a held turn's text goes back to, by thread (`ComposerDraftContext`). */
export type DraftHome = {
  stashFailedDraftForThread: (thread: string, text: string) => void;
};

type OpenedRead = {
  /** Turns waiting for this page. */
  held: PendingSend[];
  /** A turn stopped waiting (the cap ran out) and went out before the page landed. */
  overtaken: boolean;
  finished: Promise<boolean>;
};

/** Chats whose newest page is being read while their cached page is on screen, by chat id. */
const openReads = new Map<string, OpenedRead>();

/** The file layer loads expo-file-system: only a file left behind at sign-out needs it. */
function discardLocalCopy(uri: string | undefined): void {
  if (!uri) return;
  void import("@/features/attachments/model/localAttachmentFile")
    .then((file) => file.discardLocalCopy(uri))
    .catch(() => {});
}

export type OpenedPageRead = {
  /** The page landed or the read failed: held turns go out. False when one went first, so the page may hold it. */
  release: () => boolean;
  /** The view moved on: held turns stay unsent and go back to this chat's composer. */
  cancel: (home: DraftHome | null) => void;
  /** The chat is gone: held turns stay unsent and go back to New Chat's composer. */
  chatGone: (home: DraftHome | null) => void;
};

/**
 * Hands turns that never went out back to a composer, text and file. A retried
 * send keeps its Retry on its chat unless the chat is gone. With no composer
 * (signed out) only the file's local copy is cleaned up.
 */
function giveBack(turns: PendingSend[], thread: string, home: DraftHome | null, chatGone: boolean): void {
  for (const turn of turns) {
    if (turn.retryingRejected && !chatGone) continue;
    const draft = turn.options.composerDraft ?? { text: turn.content, attachment: null };
    if (!home) {
      discardLocalCopy(draft.attachment?.localUri);
      continue;
    }
    home.stashFailedDraftForThread(thread, draft.text);
    // Queued once the view that moved on has settled: a composer still listening for the old thread
    // (its effect cleans up after this one) must not take the file into the thread now shown.
    const file = draft.attachment;
    if (file) void Promise.resolve().then(() => queueComposerAttachment(file, thread));
  }
}

/**
 * The route loader reads a chat's newest page while the cached page is on
 * screen and Send already works. A turn sent meanwhile is painted at once but
 * waits here before it goes out, so the page can never hold it and merges
 * without guessing which of its rows are the turn's.
 */
export function beginOpenedPageRead(chatId: string): OpenedPageRead {
  let finish!: (sendable: boolean) => void;
  const read: OpenedRead = {
    held: [],
    overtaken: false,
    finished: new Promise((resolve) => { finish = resolve; }),
  };
  openReads.set(chatId, read);
  const end = (sendable: boolean) => {
    if (openReads.get(chatId) === read) openReads.delete(chatId);
    finish(sendable);
    return read.held.splice(0);
  };
  return {
    release: () => {
      end(true);
      return !read.overtaken;
    },
    cancel: (home) => giveBack(end(false), chatId, home, false),
    chatGone: (home) => giveBack(end(false), COMPOSER_NEW_THREAD_KEY, home, true),
  };
}

/**
 * Whether `turn` may go out on `chatId`: at once when no page is being read for
 * the chat, else when the read ends, or after the cap. False when the chat is
 * gone or the view moved on; the turn then comes back as a draft.
 */
export function whenOpenedPageSettled(chatId: string | null, turn?: PendingSend | null): Promise<boolean> {
  const read = chatId ? openReads.get(chatId) : undefined;
  if (!read) return Promise.resolve(true);
  if (turn) read.held.push(turn);
  return new Promise((resolve) => {
    const cap = setTimeout(() => {
      read.overtaken = true;
      const index = turn ? read.held.indexOf(turn) : -1;
      if (index >= 0) read.held.splice(index, 1);
      resolve(true);
    }, OPENED_PAGE_WAIT_MS);
    void read.finished.then((sendable) => {
      clearTimeout(cap);
      resolve(sendable);
    });
  });
}
