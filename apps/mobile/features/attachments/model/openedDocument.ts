import { Directory, File, Paths } from "expo-file-system";

import type { PendingAttachment } from "@/features/attachments/model/attachments";
import { discardLocalCopy } from "@/features/attachments/model/localAttachmentFile";
import type { OpenedFileInfo } from "@/features/attachments/model/openedDocumentCopy";
import { getSessionGeneration, hasSessionToken } from "@/lib/auth";
import { createListenerSet } from "@/lib/listenerSet";

/**
 * A file another app opened in Recall (iOS: Open in, or Recall in the share sheet's app
 * row; Android: Open with, or Share), held until New chat takes it into its composer.
 *
 * It belongs to the account whose sign-in was confirmed when it came, and only that account
 * takes it. One that came before a sign-in was confirmed (the sign-in screen, or a launch
 * whose saved sign-in the API has not answered for yet) belongs to no account: whoever
 * signs in takes it once the API confirms them, so a saved sign-in that turns out revoked
 * or expired (and signs out) neither takes it nor drops it.
 */
type OpenedDocument = {
  uri: string;
  info: OpenedFileInfo;
  /** The confirmed sign-in session it came in; null when there was none. */
  owner: number | null;
};

let held: OpenedDocument | null = null;
/** The session the chat saw the API confirm (or offline, where it cannot ask); null while none is. */
let confirmedSession: number | null = null;
/** Counts the files taken: a copy that a newer file overtook gives way to it. */
let claims = 0;
const listeners = createListenerSet();

/** `a/./b/../c` as `a/c`: a path is compared as the file system resolves it. */
function resolvedPath(path: string): string {
  const parts: string[] = [];
  for (const part of path.split("/")) {
    if (part === "..") parts.pop();
    else if (part && part !== ".") parts.push(part);
  }
  return `/${parts.join("/")}${path.endsWith("/") ? "/" : ""}`;
}

/**
 * A `file:` URL's path as the file system reads it: fully decoded (an encoded "/" is a "/"
 * there too), its dot segments resolved. iOS spells the container `/private/var/…` as well
 * as `/var/…`.
 */
function filePath(uri: string): string | null {
  if (!/^file:\/\//i.test(uri)) return null;
  let decoded: string;
  try {
    decoded = decodeURIComponent(uri.replace(/^file:\/\//i, ""));
  } catch (error) {
    // A malformed escape names no file iOS made.
    if (error instanceof URIError) return null;
    throw error;
  }
  return resolvedPath(decoded).replace(/^\/private\/var\//, "/var/");
}

/** This iOS app's container: the folder that holds Documents/, Library/ and tmp/. */
function containerPath(): string | null {
  const documents = filePath(Paths.document.uri);
  return documents && /\/Documents\/$/.test(documents) ? documents.replace(/Documents\/$/, "") : null;
}

/** Where iOS copies a file opened in an app: Documents/Inbox, or tmp/<bundle id>-Inbox. */
const INBOX_COPY = /^(?:Documents\/Inbox|tmp\/[^/]+-Inbox)\/([^/]+)$/;

/** A failure this file works around, by kind only: a file system error can carry the file's path. */
function warn(stage: string, error: unknown): void {
  console.warn("[openedFile]", { stage, error: error instanceof Error ? error.name : typeof error });
}

/**
 * The copy iOS made in this app's container when another app opened a file in Recall
 * (`LSSupportsOpeningDocumentsInPlace` is false): a file directly inside its Inbox. Only
 * such a copy is Recall's to delete; any other file URL is the original's.
 */
export function isOpenedInboxFile(uri: string): boolean {
  const path = filePath(uri);
  const container = containerPath();
  if (!path || !container || !path.startsWith(container)) return false;
  return INBOX_COPY.test(path.slice(container.length));
}

/** A file of Recall's own container that is no Inbox copy: its private data, never an opened file. */
function isOwnFile(uri: string): boolean {
  const path = filePath(uri);
  const container = containerPath();
  return Boolean(path && container && path.startsWith(container)) && !isOpenedInboxFile(uri);
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

/** The confirmed session now, or null: a file coming now is its, and only it may take one. */
function confirmedNow(): number | null {
  const session = getSessionGeneration();
  return confirmedSession === session && hasSessionToken() ? session : null;
}

/**
 * The chat says whether the API has confirmed this sign-in (or the phone is offline, where it
 * cannot ask). Until it has, a file waits and belongs to no account.
 */
export function setOpenedDocumentSignIn(confirmed: boolean): void {
  confirmedSession = confirmed ? getSessionGeneration() : null;
}

/** Hold a file another app opened in Recall; it replaces one New chat has not taken yet. */
export function receiveOpenedDocument(uri: string, info: OpenedFileInfo = {}): void {
  if (isOwnFile(uri) || inboxCopyGone(uri)) return;
  const previous = held;
  held = { uri, info, owner: confirmedNow() };
  if (previous && previous.uri !== uri) deleteInboxCopy(previous.uri);
  listeners.emit();
}

export function subscribeOpenedDocument(listener: () => void): () => void {
  return listeners.subscribe(listener);
}

/**
 * New chat takes the held file, copied into the cache and checked like a pick (size, type).
 * Null when nothing is held, when no confirmed sign-in may take it yet, when it belonged to
 * an account since signed out, when a newer file overtook it, or when the account changed
 * while it was copied (a copy that failed then says nothing: the sign-in screen has no
 * composer). A file Recall cannot attach throws its AttachmentError.
 */
export async function claimOpenedDocument(): Promise<PendingAttachment | null> {
  const document = held;
  const session = confirmedNow();
  if (!document || session === null) return null;
  held = null;
  const claim = ++claims;
  if (document.owner !== null && document.owner !== session) {
    deleteInboxCopy(document.uri);
    return null;
  }
  try {
    const { copyOpenedDocument } = await import("@/features/attachments/model/openedDocumentCopy");
    const pending = await copyOpenedDocument(document.uri, document.info);
    if (session === getSessionGeneration() && claim === claims) return pending;
    discardLocalCopy(pending.localUri);
    return null;
  } catch (error) {
    if (session !== getSessionGeneration() || claim !== claims) return null;
    throw error;
  } finally {
    deleteInboxCopy(document.uri);
  }
}

/**
 * Sign-out: a file that came while that account was signed in goes with it. One that came
 * before a sign-in was confirmed was no account's, and waits for the next sign-in.
 */
export function clearOpenedDocument(): void {
  confirmedSession = null;
  if (!held || held.owner === null) return;
  deleteInboxCopy(held.uri);
  held = null;
  listeners.emit();
}

/** The Inbox folders iOS fills in this container: Documents/Inbox and each tmp/<bundle id>-Inbox. */
function inboxFolders(container: string): Directory[] {
  const folders = [new Directory(`file://${container}Documents/Inbox/`)];
  const tmp = new Directory(`file://${container}tmp/`);
  if (!tmp.exists) return folders;
  return folders.concat(tmp.list().filter((entry): entry is Directory =>
    entry instanceof Directory && /-Inbox\/?$/.test(entry.uri)));
}

/**
 * At launch: delete Inbox copies a run that ended before New chat took them left behind (iOS
 * keeps them, and backs them up). Only files directly inside an Inbox, never the one held now.
 */
export function sweepOpenedInboxCopies(): void {
  const container = containerPath();
  if (!container) return;
  const keep = held ? filePath(held.uri) : null;
  try {
    for (const folder of inboxFolders(container)) {
      if (!folder.exists) continue;
      for (const entry of folder.list()) {
        if (entry instanceof File && isOpenedInboxFile(entry.uri) && filePath(entry.uri) !== keep) entry.delete();
      }
    }
  } catch (error) {
    warn("sweep_inbox", error);
  }
}
