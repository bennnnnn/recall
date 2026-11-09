/** Shared profile display + edit helpers for Settings and Avatar. */

export function sanitizeDisplayName(raw: string): string | null {
  const name = raw.trim().replace(/\s+/g, " ");
  if (!name || name.length > 80) return null;
  return name;
}

/**
 * "bini" is shown as "Bini": the first letter capitalised the way the app's language
 * writes it (Turkish "i" is "İ"), the rest as the account has it.
 */
export function capitalisedName(name: string, language: string): string {
  const [initial = "", ...rest] = Array.from(name);
  return initial.toLocaleUpperCase(language || undefined) + rest.join("");
}

/** The account's name as every screen shows it, or `fallback` when it has none. */
export function getDisplayName(
  name: string | null | undefined,
  fallback: string,
  language: string,
): string {
  const trimmed = name?.trim();
  return trimmed ? capitalisedName(trimmed, language) : fallback;
}

export function getInitials(name: string | null | undefined, language: string): string {
  if (!name?.trim()) return "?";
  const letters = name
    .trim()
    .split(/\s+/)
    .map((part) => Array.from(part)[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toLocaleUpperCase(language || undefined);
  return letters || "?";
}
