/** Quote mermaid node labels that contain raw parentheses.
 *
 * Unquoted `E[Grind Beans (Medium Grind)]` is invalid Mermaid and the
 * WebView parse-fails. Linear scan — no nested regex.
 */

export function sanitizeMermaidNodeLabels(text: string): string {
  if (!text.includes("(") && !text.includes(")")) return text;
  const pieces: string[] = [];
  let index = 0;
  while (index < text.length) {
    const bracket = text.indexOf("[", index);
    if (bracket < 0) {
      pieces.push(text.slice(index));
      break;
    }
    pieces.push(text.slice(index, bracket));
    if (text[bracket + 1] === '"') {
      const close = text.indexOf('"]', bracket + 2);
      if (close < 0) {
        pieces.push(text.slice(bracket));
        break;
      }
      pieces.push(text.slice(bracket, close + 2));
      index = close + 2;
      continue;
    }
    const close = text.indexOf("]", bracket + 1);
    if (close < 0) {
      pieces.push(text.slice(bracket));
      break;
    }
    const body = text.slice(bracket + 1, close);
    if (
      (body.includes("(") || body.includes(")")) &&
      !(body.length >= 2 && body.startsWith('"') && body.endsWith('"'))
    ) {
      pieces.push('["', body.replace(/"/g, "'"), '"]');
    } else {
      pieces.push(text.slice(bracket, close + 1));
    }
    index = close + 1;
  }
  return pieces.join("");
}
