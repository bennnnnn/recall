import { isMathLike } from "@/lib/normalizeImplicitMath";
import {
  isMostlyProsePaste,
  pastedDeltaLooksLikeMath,
} from "@/lib/mathPasteNormalize";

const MATH_FENCE = /```(?:math|geometry|graph|answer)\b/i;
const MATH_MARKERS = /\$|\\(?:frac|sqrt|sum|int|lim|pi|times|div|leq|geq|neq|sin|cos|tan)|[√π∞≤≥≠×÷]/;
const MATH_ASK =
  /\b(solve|equation|algebra|calculus|derivative|integral|quadratic|polynomial|radicand|square root|simplify|factor|expand|trigonometry)\b/i;
/** Weak math signal — digits, equals, basic operators — to disambiguate "solve this mystery" from "solve 2x+3=7". */
const MATH_SIGNAL = /[0-9=+\-*/^()]|\\(?:frac|sqrt|sum|int|lim)|[√≤≥≠×÷]/;

/** True when composer text or a chat message is a math ask — not weather/chat prose. */
export function textLooksLikeMath(text: string): boolean {
  const s = text.trim();
  if (s.length < 2) return false;
  if (MATH_FENCE.test(s)) return true;
  if (isMostlyProsePaste(s)) return false;
  if (MATH_MARKERS.test(s)) return true;
  // MATH_ASK words alone (e.g. "solve this mystery") need a co-occurring math signal
  // to avoid false-positive chips in prose-heavy chats.
  if (MATH_ASK.test(s) && MATH_SIGNAL.test(s)) return true;
  if (pastedDeltaLooksLikeMath(s) || isMathLike(s)) return true;
  return false;
}

const RECENT = 8;

export function messagesLookLikeMath(contents: readonly string[]): boolean {
  const start = Math.max(0, contents.length - RECENT);
  for (let i = start; i < contents.length; i += 1) {
    if (textLooksLikeMath(contents[i] ?? "")) return true;
  }
  return false;
}
