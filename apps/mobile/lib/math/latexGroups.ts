/** A `{...}` group. An escaped brace is content, not structure. */
export function readGroup(input: string, start: number): { value: string; next: number } | null {
  if (input[start] !== "{") return null;
  let depth = 0;
  for (let i = start; i < input.length; i += 1) {
    if (input[i] === "\\" && i + 1 < input.length) {
      i += 1;
      continue;
    }
    if (input[i] === "{") depth += 1;
    else if (input[i] === "}") {
      depth -= 1;
      if (depth === 0) {
        return { value: input.slice(start + 1, i), next: i + 1 };
      }
    }
  }
  return null;
}

/** SymPy emits y{\\left(x \\right)}; these braces group one function
 * argument and are invisible in TeX. Escaped set braces never enter here. */
export function isParenthesizedArgument(value: string): boolean {
  const text = value.trim();
  if (!text.startsWith("(") || !text.endsWith(")")) return false;
  let depth = 0;
  for (let i = 0; i < text.length; i += 1) {
    if (text[i] === "\\") {
      i += 1;
      continue;
    }
    if (text[i] === "(") depth += 1;
    if (text[i] === ")") depth -= 1;
    if (depth === 0 && i < text.length - 1) return false;
  }
  return depth === 0;
}
