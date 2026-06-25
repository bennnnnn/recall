// Shared drawer control — avoids circular imports between _layout and ConversationList
let _open: (() => void) | null = null;
let _close: (() => void) | null = null;

export function registerDrawer(open: () => void, close: () => void) {
  _open = open;
  _close = close;
}

export function openDrawer() { _open?.(); }
export function closeDrawer() { _close?.(); }

// Shared "start a new chat" action — registered by the chat screen so the
// drawer can trigger it without prop drilling or fragile route params.
let _newChat: (() => void) | null = null;

export function registerNewChat(fn: () => void) {
  _newChat = fn;
}

export function startNewChatGlobal() {
  _newChat?.();
}
