/**
 * A JSON card's fence arrives a few characters at a time while the reply
 * streams. Until its JSON parses, the card draws nothing rather than an error.
 */
export function isUnfinishedJson(content: string): boolean {
  try {
    JSON.parse(content);
    return false;
  } catch {
    return true;
  }
}
