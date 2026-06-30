/** Typical bubble height for FlashList layout hints (variable-height items). */
export const ESTIMATED_MESSAGE_HEIGHT = 88;

export function messageListItemType(item: { id: string; role: string }): string {
  if (item.id === "streaming") return "streaming";
  return item.role;
}
