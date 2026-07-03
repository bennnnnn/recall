/** Typical bubble height for FlashList layout hints (variable-height items). */
export const ESTIMATED_MESSAGE_HEIGHT = 88;

/** Delay post-stream UI (actions, link previews, sources) so layout settles once. */
export const STREAM_LAYOUT_SETTLE_MS = 280;

export function messageListItemType(item: { id: string; role: string }): string {
  return item.role;
}

export function messageListKey(item: { id: string; renderKey?: string }): string {
  return item.renderKey ?? item.id;
}
