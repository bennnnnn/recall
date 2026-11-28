/**
 * A formula as words, for every ear: a screen reader's label and read-aloud speak the same
 * line ("v subscript f - v subscript i, all over t"). A drawing groups by position, a
 * fraction bar or a raised exponent; spoken, the grouping is said: a sum over a bar is
 * "all over", one under it "the quantity", and a sum under a root or in a power ends on
 * a pause, so what follows is not heard as part of it. The words are the app's language's
 * (lib/math/speechWords.ts); English is shown in these notes.
 */
import { followsDirectly, isMixedNumber, joinsDirectly } from "@/lib/math/formulaText";
import { isPrimeScript } from "@/lib/math/glyphs";
import { DEGREE_RING, parseSimpleLatex } from "@/lib/math/latexParse";
import {
  ACCENT_WORD,
  fillWord,
  mathSpeechWords,
  type MathSpeechWord,
  type MathSpeechWords,
} from "@/lib/math/speechWords";
import type { MathSegment } from "@/lib/math/textTypes";

const MAX_SPEAK_MATH_DEPTH = 12;
// A pause the words add. It is said as a comma, unless the line already pauses there (the
// formula's own comma, a closing bracket, its end).
const PAUSE = "\u0000";
// What splits a spoken run into terms; a leading sign belongs to its number (-1 over 2).
const SPOKEN_OPERATOR = /[+\-−±∓=<>≤≥≠≈→,]/;
const LEADING_SIGN = /^\s*[+\-−]/;
// A new term after a power: "x to the power of n, - 1", not x^(n-1). "Squared" closes itself.
const OPENS_WITH_OPERATOR = /^\s*[+\-−±∓=<>≤≥≠≈×·⋅/÷]/;
// A mixed number's fraction in English words: 2 and 1 half, 1 and 3 quarters.
const DENOMINATOR_WORDS: Record<string, [string, string]> = {
  "2": ["half", "halves"],
  "3": ["third", "thirds"],
  "4": ["quarter", "quarters"],
  "5": ["fifth", "fifths"],
  "6": ["sixth", "sixths"],
  "7": ["seventh", "sevenths"],
  "8": ["eighth", "eighths"],
  "9": ["ninth", "ninths"],
  "10": ["tenth", "tenths"],
};

type Neighbours = { prev: MathSegment | undefined; next: MathSegment | undefined };

// The words of the formula being spoken: `spokenFormula` reads them once, then walks.
let speech: MathSpeechWords = mathSpeechWords();

/** One word in the app's language, its blanks filled. */
function word(key: MathSpeechWord, values: Record<string, string> = {}): string {
  return fillWord(speech.words[key], values);
}

/** More than one term once spoken: it needs its grouping said. A root or a fraction
 * inside counts too ("the square root of 2 over 2" is heard either way). */
function isCompound(segments: MathSegment[]): boolean {
  return segments.some((segment, index) => {
    switch (segment.type) {
      case "text":
      case "upright":
        return SPOKEN_OPERATOR.test(index === 0 ? segment.value.replace(LEADING_SIGN, "") : segment.value);
      case "sup":
      case "sub":
        return scriptIsCompound(segment);
      case "frac":
      case "sqrt":
        return true;
      default:
        return isCompound(segment.body);
    }
  });
}

function scriptIsCompound(segment: Extract<MathSegment, { type: "sup" | "sub" }>): boolean {
  return segment.body ? isCompound(segment.body) : SPOKEN_OPERATOR.test(segment.value.replace(LEADING_SIGN, ""));
}

/** Spoken operators. The parser has already turned `\times` into `×`. */
function speakPlainMath(value: string): string {
  const plusMinus = ` ${word("plus_minus")} `;
  const times = ` ${word("times")} `;
  const dot = ` ${word("dot")} `;
  let out = value
    .replaceAll("±", plusMinus)
    .replaceAll("×", times)
    .replaceAll("⋅", dot)
    .replaceAll("·", dot);
  if (out.includes("\\")) {
    out = out
      .replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, (_, num: string, den: string) => word("over", { num, den }))
      .replace(/\\sqrt\{([^{}]+)\}/g, (_, x: string) => word("sqrt", { x }))
      .replace(/\\times(?![a-zA-Z])/g, times)
      .replace(/\\cdot(?![a-zA-Z])/g, dot)
      .replace(/\\pm(?![a-zA-Z])/g, plusMinus)
      .replace(/\\[a-zA-Z]+/g, " ")
      .replace(/[{}]/g, "");
  }
  return out;
}

/** A script in words; `runsOn` when it ends on its exponent ("to the power of n"). */
function speakScript(segment: Extract<MathSegment, { type: "sup" | "sub" }>, depth: number): { words: string; runsOn: boolean } {
  const kind = segment.type;
  const spoken = (
    segment.body
      ? speakMathSegments(segment.body, depth + 1)
      : depth >= MAX_SPEAK_MATH_DEPTH ? segment.value : speakMathSegments(parseSimpleLatex(segment.value), depth + 1)
  ).trim();
  const said = (words: string, runsOn = false) => ({ words, runsOn });
  if (!spoken) return said("");
  if (kind === "sub") return said(` ${word("subscript", { x: spoken })}`);
  // `30^\circ` is thirty degrees, never a power.
  if (spoken === DEGREE_RING) return said(` ${word("degrees")}`);
  // f′ is "f prime" as a screen reader says the glyph, never a power.
  if (isPrimeScript(spoken)) return said(spoken);
  if (spoken === "2") return said(` ${word("squared")}`);
  if (spoken === "3") return said(` ${word("cubed")}`);
  return said(` ${word("power", { x: spoken })}`, true);
}

/** A power said with words that run on ("to the power of n") is closed before a new term. */
function speakScriptBefore(segment: Extract<MathSegment, { type: "sup" | "sub" }>, depth: number, next?: MathSegment): string {
  const { words, runsOn: open } = speakScript(segment, depth);
  const nextText = next?.type === "text" || next?.type === "upright" ? next.value : "";
  const runsOn = open && OPENS_WITH_OPERATOR.test(nextText);
  // H₂O is "H subscript 2 O": a letter written after the script is a word of its own.
  const gap = /^[\p{L}\p{N}]/u.test(nextText) ? " " : "";
  return `${words}${scriptIsCompound(segment) || runsOn ? PAUSE : gap}`;
}

/** 2\frac{1}{2} after its whole number: "and 1 half". */
function speakMixedFraction(segment: Extract<MathSegment, { type: "frac" }>): string {
  const num = speakMathSegments(segment.num).trim();
  const den = speakMathSegments(segment.den).trim();
  const ordinal = speech.ordinals ? DENOMINATOR_WORDS[den] : undefined;
  if (ordinal) return ` and ${num} ${ordinal[num === "1" ? 0 : 1]}`;
  return ` ${word("mixed", { num, den })}`;
}

function speakFraction(segment: Extract<MathSegment, { type: "frac" }>, depth: number, { prev, next }: Neighbours): string {
  // A number written onto the fraction is a whole part (2 and 1 half) or a factor
  // (20,000 times 0.005 over 12), never one number run into its numerator.
  if (isMixedNumber(prev, segment)) return `${speakMixedFraction(segment)}${joinsDirectly(next) ? PAUSE : ""}`;
  const times = followsDirectly(prev) ? ` ${word("times")} ` : "";
  const num = speakMathSegments(segment.num, depth + 1).trim();
  const den = speakMathSegments(segment.den, depth + 1).trim();
  const groupedNum = isCompound(segment.num);
  const groupedDen = isCompound(segment.den);
  const under = groupedDen ? word("quantity", { x: den }) : den;
  const fraction = word(groupedNum ? "all_over" : "over", { num, den: under });
  // ½mv² is "1 over 2, m v squared": the factor after a fraction is not its denominator.
  return `${times}${fraction}${groupedNum || groupedDen || joinsDirectly(next) ? PAUSE : ""}`;
}

function speakRoot(segment: Extract<MathSegment, { type: "sqrt" }>, depth: number, prev?: MathSegment): string {
  // 2√3 is "2 times the square root of 3", not "2the square root of 3".
  const times = followsDirectly(prev) ? ` ${word("times")} ` : "";
  const body = speakMathSegments(segment.body, depth + 1).trim();
  const degree = segment.index
    ? speakMathSegments(segment.index, depth + 1).trim()
    : segment.degree
      ? speakMathSegments(parseSimpleLatex(segment.degree), depth + 1).trim()
      : "";
  const compound = isCompound(segment.body);
  const key: MathSpeechWord = !degree ? "sqrt" : degree === "3" ? "cbrt" : "root";
  // A sum under the root ends on a pause. Where the language says the root after its body
  // (Hindi "x+1 का वर्गमूल"), the root word cannot mark where the sum starts: it is said
  // as a quantity, as a fraction's grouped denominator is ("कोष्ठक में x+1, का वर्गमूल").
  const opensAfter = !/\{x\}\s*$/.test(speech.words[key]);
  const x = compound && opensAfter ? word("quantity", { x: body }) : body;
  return `${times}${word(key, { n: degree, x })}${compound ? PAUSE : ""}`;
}

/** Read-aloud walks the same segments as copy. A `[^}]+` fraction regex
 * never matches `x^{2}`, and stripping the leftover braces speaks `fracx^24`. */
function speakMathSegments(segments: MathSegment[], depth = 0): string {
  if (depth > MAX_SPEAK_MATH_DEPTH) {
    return segments.map((segment) => ("value" in segment ? segment.value : "")).join(" ");
  }
  return segments.map((segment, index) => {
    switch (segment.type) {
      case "text":
      case "upright":
        return speakPlainMath(segment.value);
      case "sup":
      case "sub":
        return speakScriptBefore(segment, depth, segments[index + 1]);
      case "frac":
        return speakFraction(segment, depth, { prev: segments[index - 1], next: segments[index + 1] });
      case "sqrt":
        return speakRoot(segment, depth, segments[index - 1]);
      case "cancel":
        return speakMathSegments(segment.body, depth + 1);
      case "accent": {
        const body = speakMathSegments(segment.body, depth + 1).trim();
        return word(ACCENT_WORD[segment.kind], { x: body });
      }
      default: {
        const _exhaustive: never = segment;
        return _exhaustive;
      }
    }
  }).join("");
}

/** The formula as words: a screen reader's label and read-aloud, never a `\\command`. */
export function spokenFormula(latex: string): string {
  speech = mathSpeechWords();
  return speakMathSegments(parseSimpleLatex(latex))
    .replace(/\s+/g, " ")
    .replace(/ ?\0[\0 ]*(?=[,;:.!?)\]|]|$)/g, "")
    .replace(/ ?\0[\0 ]*/g, ", ")
    .trim();
}
