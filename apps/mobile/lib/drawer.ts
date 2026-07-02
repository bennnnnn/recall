import type { Chat } from "@/lib/api";

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

let _openSearch: (() => void) | null = null;

/** Open the history drawer with search focused (registered by ConversationList). */
export function registerDrawerSearch(fn: (() => void) | null) {
  _openSearch = fn;
}

export function openDrawerSearch() {
  _open?.();
  _openSearch?.();
}

// Shared "start a new chat" action — registered by the chat screen so the
// drawer can trigger it without prop drilling or fragile route params.
let _newChat: (() => void) | null = null;

export function registerNewChat(fn: () => void) {
  _newChat = fn;
}

export function startNewChatGlobal() {
  _newChat?.();
}

/** Patch a chat row in the drawer list (e.g. when auto-title arrives). */
export type ChatListPatch = {
  title?: string | null;
  pinned?: boolean;
};

let _patchChat: ((chatId: string, patch: ChatListPatch) => void) | null = null;

export function registerChatPatcher(fn: ((chatId: string, patch: ChatListPatch) => void) | null) {
  _patchChat = fn;
}

export function patchChatGlobal(chatId: string, patch: ChatListPatch) {
  _patchChat?.(chatId, patch);
}

/** Insert a chat into the drawer list after the first reply (see insertChatIntoGroups). */
let _insertChat: ((chat: Chat) => void) | null = null;

export function registerChatInserter(fn: ((chat: Chat) => void) | null) {
  _insertChat = fn;
}

export function insertChatGlobal(chat: Chat) {
  _insertChat?.(chat);
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
