import { splitInlineMath } from "@/lib/markdown/inlineMath";
import { formulaText } from "@/lib/math/text";

/**
 * A message hit's line as the drawer shows it. The server sends the words without their
 * markdown, each formula kept whole between `$` marks and a dollar it knows is not maths
 * (code's `$HOME`) escaped as `\$` (`modules/search/snippet.py`). A formula reads as one
 * line of symbols, never its TeX: `$v_0 = 20\,\mathrm{m/s}$` is "v_0 = 20 m/s". The
 * highlight is cut from this line, so it lands on the words the reader sees.
 */
export function snippetText(content: string): string {
  return splitInlineMath(content)
    .map((part) => (part.type === "math" ? formulaText(part.value) : part.value.replaceAll("\\$", "$")))
    .join("");
}
