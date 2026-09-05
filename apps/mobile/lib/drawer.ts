import type { Chat } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";

// Shared drawer control — avoids circular imports between DrawerShell and ConversationList
let _open: (() => void) | null = null;
let _close: (() => void) | null = null;

export function registerDrawer(open: () => void, close: () => void) {
  _open = open;
  _close = close;
}

export function openDrawer() {
  _open?.();
}
export function closeDrawer() {
  _close?.();
}

// Shared "start a new chat" action — registered by the chat screen so the
// drawer can trigger it without prop drilling or fragile route params.
export type StartNewChatOptions = { force?: boolean };
export type StartNewChatFn = (opts?: StartNewChatOptions) => void;

let _newChat: StartNewChatFn | null = null;

export function registerNewChat(fn: StartNewChatFn | null) {
  _newChat = fn;
}

export function startNewChatGlobal(opts?: StartNewChatOptions) {
  _newChat?.(opts);
}

// Selecting a title result can keep the same route/chat id. Explicitly cancel
// the previous message target even when there is no route change to observe.
let _clearChatHighlight: (() => void) | null = null;
export function registerChatHighlightClearer(clear: (() => void) | null) {
  _clearChatHighlight = clear;
}
export function clearChatHighlightGlobal() {
  _clearChatHighlight?.();
}

/** Active chat id on the home screen — drawer deletes use this to avoid orphans. */
let _activeChatId: string | null = null;

export function setActiveChatIdGlobal(chatId: string | null) {
  _activeChatId = chatId;
}

export function getActiveChatIdGlobal(): string | null {
  return _activeChatId;
}

/** True when a delete batch includes the chat currently open on the home screen. */
export function deletedIncludesActiveChat(
  deletedIds: readonly string[],
  activeChatId: string | null = getActiveChatIdGlobal(),
): boolean {
  if (!activeChatId) return false;
  return deletedIds.includes(activeChatId);
}

/** Send the home screen back to a fresh chat if a delete just removed the open one. */
export function abandonActiveChatIfDeleted(deletedIds: readonly string[]) {
  if (!deletedIncludesActiveChat(deletedIds)) return;
  startNewChatGlobal({ force: true });
}

/** Patch a chat row in the drawer list (e.g. when auto-title arrives). */
export type ChatListPatch = Partial<Chat>;

let _patchChat: ((chatId: string, patch: ChatListPatch) => void) | null = null;

export function registerChatPatcher(fn: ((chatId: string, patch: ChatListPatch) => void) | null) {
  _patchChat = fn;
}

export function patchChatGlobal(chatId: string, patch: ChatListPatch) {
  _patchChat?.(chatId, patch);
}

/** Move a chat between active and archived sections in the drawer list. */
let _moveChatArchive: ((chatId: string, archived: boolean) => void) | null = null;

export function registerChatArchiveMover(
  fn: ((chatId: string, archived: boolean) => void) | null,
) {
  _moveChatArchive = fn;
}

export function moveChatArchiveGlobal(chatId: string, archived: boolean) {
  _moveChatArchive?.(chatId, archived);
}

/** Insert a chat into the drawer list after the first reply (see insertChatIntoGroups). */
let _insertChat: ((chat: Chat) => void) | null = null;

export function registerChatInserter(fn: ((chat: Chat) => void) | null) {
  _insertChat = fn;
}

export function insertChatGlobal(chat: Chat) {
  _insertChat?.(chat);
}

let _removeChat: ((chatId: string) => void) | null = null;

export function registerChatRemover(fn: ((chatId: string) => void) | null) {
  _removeChat = fn;
}

export function removeChatGlobal(chatId: string) {
  _removeChat?.(chatId);
}

const _pendingTitleChatIds = new Set<string>();
let _onTitlePendingChange: (() => void) | null = null;

/** Mark a chat as waiting for auto-title (header + drawer show "Generating…"). */
export function setChatTitleGenerating(chatId: string | null) {
  _pendingTitleChatIds.clear();
  if (chatId) _pendingTitleChatIds.add(chatId);
  _onTitlePendingChange?.();
}

export function isChatTitleGenerating(chatId: string): boolean {
  return _pendingTitleChatIds.has(chatId);
}

export function subscribeChatTitleGenerating(fn: () => void) {
  _onTitlePendingChange = fn;
  return () => {
    if (_onTitlePendingChange === fn) _onTitlePendingChange = null;
  };
}

/** Metadata changes shared by the drawer and the currently open conversation. */
type ChatChangeListener = (chatId: string, patch: Partial<Chat> | null) => void;
const chatChangeListeners = new Set<ChatChangeListener>();
let mutationSession = -1;
const chatMutationRevisions = new Map<string, number>();

export function getChatMutationRevision(chatId: string): number {
  if (mutationSession !== getSessionGeneration()) {
    mutationSession = getSessionGeneration();
    chatMutationRevisions.clear();
  }
  return chatMutationRevisions.get(chatId) ?? 0;
}

export function publishChatChange(chatId: string, patch: Partial<Chat> | null): void {
  chatMutationRevisions.set(chatId, getChatMutationRevision(chatId) + 1);
  for (const listener of chatChangeListeners) listener(chatId, patch);
}

export function subscribeChatChanges(listener: ChatChangeListener): () => void {
  chatChangeListeners.add(listener);
  return () => { chatChangeListeners.delete(listener); };
}
