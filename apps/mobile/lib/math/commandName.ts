/**
 * A word command (`\rfloor`, `\alpha`) runs to its first non-letter, so a letter written
 * right after it joins its name: `\rfloor` then `y` reads as `\rfloory`, a command nobody
 * wrote. A space ends the name, as the keyboard's `\pi ` does.
 */
export function joinsCommandName(before: string, after: string): boolean {
  return /\\[A-Za-z]+$/.test(before) && /^[A-Za-z]/.test(after);
}
