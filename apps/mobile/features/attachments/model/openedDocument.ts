import { File, Paths } from "expo-file-system";

import type { PendingAttachment } from "@/features/attachments/model/attachments";
import { discardLocalCopy } from "@/features/attachments/model/localAttachmentFile";
import { getSessionGeneration, hasSessionToken } from "@/lib/auth";
import { createListenerSet } from "@/lib/listenerSet";

/**
 * A file another app opened in Recall (iOS: Open in, or Recall in the share sheet's app
 * row; Android: Open with, or Share), held until New chat takes it into its composer.
 *
 * It belongs to the account signed in when it came, and only that account takes it. One
 * that came while no one was signed in (the sign-in screen, or a launch that has not read
 * the saved sign-in yet) belongs to no account: whoever signs in next takes it, once the
 * API has confirmed that sign-in, so a saved sign-in that turns out expired (and signs
 * out) never takes it into a composer its sign-out then empties.
 */
type OpenedDocument = {
  uri: string;
  /** The name the other app gave it: an Android content URI does not carry one. */
  name?: string;
  /** The sign-in session it came in; null when no one was signed in. */
  owner: number | null;
};

let held: OpenedDocument | null = null;
const listeners = createListenerSet();

/**
 * A `file:` URL's path as the file system reads it: fully decoded (an encoded "/" is a "/"
 * there too). iOS spells the container `/private/var/…` as well as `/var/…`.
 */
function filePath(uri: string): string | null {
  if (!/^file:\/\//i.test(uri)) return null;
  try {
    return decodeURIComponent(uri.replace(/^file:\/\//i, "")).replace(/^\/private\/var\//, "/var/");
  } catch (error) {
    // A malformed escape names no file iOS made.
    if (error instanceof URIError) return null;
    throw error;
  }
}

function inboxPath(): string | null {
  const documents = filePath(Paths.document.uri);
  return documents ? `${documents.replace(/\/?$/, "/")}Inbox/` : null;
}

/** A failure this file works around, by kind only: a file system error can carry the file's path. */
function warn(stage: string, error: unknown): void {
  console.warn("[openedFile]", { stage, error: error instanceof Error ? error.name : typeof error });
}

/**
 * A file iOS copied into this app's Documents/Inbox when another app opened it in Recall
 * (`LSSupportsOpeningDocumentsInPlace` is false). Only a file directly inside it.
 */
export function isOpenedInboxFile(uri: string): boolean {
  const path = filePath(uri);
  const inbox = inboxPath();
  if (!path || !inbox || !path.startsWith(inbox)) return false;
  const name = path.slice(inbox.length);
  return name.length > 0 && !name.includes("/") && name !== "." && name !== "..";
}

/** iOS leaves the Inbox copy for the app to delete: once it is read, or no longer wanted. */
function deleteInboxCopy(uri: string): void {
  if (!isOpenedInboxFile(uri)) return;
  try {
    const file = new File(uri);
    if (file.exists) file.delete();
  } catch (error) {
    // The Inbox holds only files opened in Recall: one left there harms nothing.
    warn("delete_inbox_copy", error);
  }
}

/** A launch read again (a JS reload) names an Inbox file Recall already took and deleted. */
function inboxCopyGone(uri: string): boolean {
  return isOpenedInboxFile(uri) && !new File(uri).exists;
}

/** Hold a file another app opened in Recall; it replaces one New chat has not taken yet. */
export function receiveOpenedDocument(uri: string, name?: string): void {
  if (inboxCopyGone(uri)) return;
  const previous = held;
  held = { uri, name, owner: hasSessionToken() ? getSessionGeneration() : null };
  if (previous && previous.uri !== uri) deleteInboxCopy(previous.uri);
  listeners.emit();
}

export function subscribeOpenedDocument(listener: () => void): () => void {
  return listeners.subscribe(listener);
}

/**
 * New chat takes the held file, copied into the cache and checked like a pick (size, type).
 * `signInConfirmed`: the API has confirmed this session (or the phone is offline and cannot
 * ask); a file that came before anyone signed in waits for it. Null when nothing is held,
 * when the file waits, when it belonged to an account since signed out, or when the account
 * changed while it was copied. A file Recall cannot attach throws its AttachmentError.
 */
export async function claimOpenedDocument(signInConfirmed: boolean): Promise<PendingAttachment | null> {
  const document = held;
  if (!document || !hasSessionToken()) return null;
  if (document.owner === null && !signInConfirmed) return null;
  held = null;
  const session = getSessionGeneration();
  if (document.owner !== null && document.owner !== session) {
    deleteInboxCopy(document.uri);
    return null;
  }
  try {
    const { copyOpenedDocument } = await import("@/features/attachments/model/openedDocumentCopy");
    const pending = await copyOpenedDocument(document.uri, document.name);
    if (session === getSessionGeneration()) return pending;
    discardLocalCopy(pending.localUri);
    return null;
  } finally {
    deleteInboxCopy(document.uri);
  }
}

/**
 * Sign-out: a file that came while that account was signed in goes with it. One that came
 * before anyone signed in was no account's, and waits for the next sign-in.
 */
export function clearOpenedDocument(): void {
  if (!held || held.owner === null) return;
  deleteInboxCopy(held.uri);
  held = null;
  listeners.emit();
}
