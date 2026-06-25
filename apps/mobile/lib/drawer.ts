// Shared drawer control — avoids circular imports between _layout and ConversationList
let _open: (() => void) | null = null;
let _close: (() => void) | null = null;

export function registerDrawer(open: () => void, close: () => void) {
  _open = open;
  _close = close;
}

export function openDrawer() { _open?.(); }
export function closeDrawer() { _close?.(); }
