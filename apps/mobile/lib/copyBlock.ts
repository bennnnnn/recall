/**
 * What a fence whose tag leaves it open draws: code, a copy card, a final answer, or prose.
 * The tag decides first (lib/fenceRegistry.ts); only for no tag, a plain-text one and ```copy
 * does the body decide, and then by its shape, never by English words: a 9-language app
 * cannot read "Hi … Regards" or "As a …" as the mark of a draft or of advice. A draft is
 * tagged (```email, ```message, ```copy …, as the prompt asks); an untagged fence of
 * prose reads as prose, in every language.
 */
import {
  fenceIdForLang,
  fenceSpecForLang,
  isNeverCodeBlockLang,
  isPlainTextFenceLang,
  isSendableFenceLang,
} from "@/lib/fenceRegistry";
import { markdownToCopyText } from "@/lib/markdown/plain";
import { looksLikeMathFenceBody, stripEmbeddedDollarWraps } from "@/lib/math/fenceRetag";

/** Markdown structure (a quote, a heading, a list): written for the reader, not source code. */
function looksLikeMarkdownProse(content: string): boolean {
  const sample = content.slice(0, 1600).trim();
  if (/^\s*>/m.test(sample)) return true;
  if (/^#{1,6}\s/m.test(sample)) return true;
  return sample.split("\n").filter((line) => /^[-*•]\s/.test(line.trim())).length >= 2;
}

/** The app's own words when a maths fence did not draw: never a card to copy or send. */
function looksLikeFailedDiagram(content: string): boolean {
  return /^(Could not render that diagram\.?|Invalid (graph|geometry) block)/i.test(content.slice(0, 800).trim());
}

/**
 * Sentences, in any language: most of the words sit on lines of six words or more (a
 * letter's "Hi Ana," and "Thanks," are short), and code's brackets are rare among the
 * letters. "Bring your ID(s)…" or a line that ends in `;` is still a sentence; only the
 * strong evidence below makes it code.
 */
export function readsAsSentences(content: string): boolean {
  const lines = content.split("\n").map((line) => line.trim().split(/\s+/).filter(Boolean).length);
  const words = lines.reduce((sum, count) => sum + count, 0);
  const inSentences = lines.filter((count) => count >= 6).reduce((sum, count) => sum + count, 0);
  const letters = content.match(/\p{L}/gu)?.length ?? 0;
  const marks = content.match(/[{}()[\];=<>]/g)?.length ?? 0;
  return words > 0 && inSentences * 2 >= words && marks * 40 <= letters;
}

/** A line no sentence writes: a declaration, an arrow or strict comparison, a print or hook call, a tag, or `;` `{` `}` at its end. */
const SOURCE_LINE = [
  /^\s*(def|class|function|import|export|const|var|let|public|private|protected|fn|func|struct|interface|enum|package|SELECT|INSERT|UPDATE|DELETE|CREATE)\s+[\w$.{*]+.*[({=:;]/,
  /^\s*#include\b/,
  /=>|===|!==|::|\+\+|&&|\|\|/,
  /\b(console\.\w+|print|fmt\.Print\w*|System\.out\.\w+|useState|useEffect)\(/,
  /^\s*<\/?[a-z][\w-]*[\s/>]/,
  /[;{}]\s*$/,
];

/**
 * Source code by strong evidence only: two such lines, or more than half the lines. A draft the
 * model tagged (```email, ```linkedin, ```copy) is code only so: "Liebe Kolleg(inn)en", a
 * phone number "+1(555)" or an indented line of a poem kept its card on main and keeps it.
 */
function looksLikeSourceCode(content: string): boolean {
  const lines = content.slice(0, 2000).split("\n").filter((line) => line.trim());
  const source = lines.filter((line) => SOURCE_LINE.some((rule) => rule.test(line))).length;
  return source >= 2 || (source >= 1 && source * 2 > lines.length);
}

/** Heuristic: content is source code, not copy-ready prose. */
export function looksLikeCode(content: string): boolean {
  if (looksLikeMarkdownProse(content)) return false;
  if (looksLikeMathFenceBody(content)) return false;
  if (readsAsSentences(content)) return looksLikeSourceCode(content);
  const sample = content.slice(0, 2000);
  // Keywords as code spells them: "Class starts at 9" or "Update the wiki" opens
  // a sentence in a message, and read as code it lost the draft its card.
  if (
    /^\s*(def |class |function |import |export |const |var |public |private |protected |#include |package |func |fn |interface |type |enum |struct |impl |module |namespace |using |SELECT |CREATE |INSERT |UPDATE |DELETE )/m.test(
      sample,
    ) ||
    /^\s*(<!DOCTYPE|<\/?[a-z][\w-]*[\s/>])/im.test(sample)
  ) {
    return true;
  }
  // `Let me know...` is one of the most common message openings. Treat
  // lowercase `let` as code only when it has declaration syntax.
  if (/^\s*let\s+[A-Za-z_$][\w$]*\s*(?::[^=\n;]+)?=/m.test(sample)) {
    return true;
  }
  if (/^\s{4}\S/m.test(sample) || /^\t+\S/m.test(sample)) return true;
  // JSON or a literal opens on a bracket and a value; a draft opens on a "[Name]" placeholder.
  if (/^\s*[\[{]\s*(?:["'{[\d-]|$)/m.test(sample.slice(0, 200)) && /[;\}\],]/.test(sample)) return true;
  if (/^\s*(\/\/|\/\*|#(?!!)|\*)\s/m.test(sample)) return true;
  const mentionsLangPlusPlus = /\bC\+\+/m.test(sample);
  if (
    !mentionsLangPlusPlus &&
    /(\+\+|::|!==|===|!=|=>|\)\s*\{|\)\s*=>|;\s*$)/m.test(sample)
  ) {
    return true;
  }
  if (/^\s*@\w+|^\s*<\w+[\s/>]/.test(sample)) return true;
  if (/^\s*(if|for|while|switch|return|await|async)\s*[\(\{]/m.test(sample))
    return true;
  if (
    /\b(console\.(log|error|warn|debug)|print\(|fmt\.Print|System\.out|useState\(|useEffect\()/m.test(
      sample,
    )
  ) {
    return true;
  }
  // A call touches its parenthesis; prose puts a space before an aside
  // ("Friday (Oct 24)").
  if (
    /\w\([^)]*\)\s*[;{]?/m.test(sample) &&
    /[{}();]/.test(sample) &&
    sample.split("\n").length >= 2
  ) {
    return true;
  }
  return false;
}

/** Route to syntax-highlighted CodeBlock instead of copy/plain prose. */
export function shouldRenderAsCodeBlock(
  lang: string,
  content: string,
): boolean {
  if (looksLikeFailedDiagram(content)) return false;
  if (looksLikeMarkdownProse(content)) return false;
  if (isSendableFenceLang(lang) && !looksLikeSourceCode(content)) return false;
  if (isExplicitCodeLang(lang)) return true;
  return looksLikeCode(content);
}

/**
 * A tagged draft is the draft, whatever its language, unless its shape says it is not one:
 * empty, the developer word "fence" leaked into it, a nested fence or a heading (the model
 * used the tag as an example and swallowed the rest of the reply), or source code.
 */
export function looksLikeExplicitDraftContent(content: string): boolean {
  const trimmed = content.trim();
  if (!trimmed) return false;
  if (/^fence!?\b/i.test(trimmed)) return false;
  if (trimmed.includes("```")) return false;
  if (/^#{1,6}\s/m.test(trimmed)) return false;
  return !looksLikeSourceCode(trimmed);
}

export function isStructuredDraftLang(lang: string): boolean {
  return fenceSpecForLang(lang)?.draft ?? false;
}

/** Remove the literal developer term shown in the reported malformed card. */
export function draftFenceProseText(content: string): string {
  return content
    .split("\n")
    .filter((line) => !/^\s*fence!?\s*$/i.test(line))
    .join("\n")
    .trim();
}

/** Fences that should render as normal body text — not CopyBlock or CodeBlock. */
export function shouldRenderAsPlainProseFence(
  lang: string,
  content: string,
): boolean {
  // An explicit copy tag can contain any language. Keep genuine copy fenced;
  // unwrap only what has no draft's shape so it reads as normal prose.
  if (fenceIdForLang(lang) === "copy") return !looksLikeExplicitDraftContent(content);
  if (looksLikeMarkdownProse(content)) return true;
  if (looksLikeFailedDiagram(content)) return true;
  if (looksLikeCode(content)) return false;
  if (isExplicitCodeLang(lang)) return false;
  return isSendableFenceLang(lang) || isPlainTextFenceLang(lang);
}

// Characters a bare simplified algebraic expression is built from — no
// English words can survive this class alongside a digit/operator, so it's
// safe to allow letters here without a prose false-positive.
const MATH_ANSWER_CHARS_RE = /^[0-9a-zA-Z+\-*/^±√!(){}\\_.,\s]+$/;
// Two real (3+ letter) words in a row means prose, not a bare expression —
// "the answer" would otherwise slip through MATH_ANSWER_CHARS_RE above.
const TWO_WORDS_RE = /\b[a-zA-Z]{3,}\b\s+\b[a-zA-Z]{3,}\b/;

/** Short numeric / boxed math final — AnswerBlock only; not every equation. */
export function looksLikeMathAnswer(content: string): boolean {
  const sample = content.trim();
  if (!sample || sample.length > 80) return false;
  if (/\n/.test(sample)) return false;
  // A lone variable or "2 + Y" mentioned in prose is not a final-answer card.
  if (/^[A-Za-z]$/.test(sample)) return false;
  if (/^\d+\s*[+\-*/]\s*[A-Za-z]\s*$/.test(sample)) return false;
  if (/^[A-Za-z]\s*[+\-*/]\s*\d+\s*$/.test(sample)) return false;
  // Bare number, optional % / factorial: 120, 5!, -3.5
  if (/^[±+\-]?\d+(?:[.,]\d+)?(?:\s*[%])?!?$/.test(sample)) return true;
  if (/^\$[^$\n]+\$$/.test(sample)) {
    return looksLikeMathAnswer(sample.slice(1, -1));
  }
  if (/^\\boxed\{[^}]+\}$/.test(sample)) return true;
  // Short scalar assignment final: x = 2, n = 120 (not multi-step / worded).
  if (/^[a-zA-Z]\s*=\s*[±+\-]?\d+(?:[.,]\d+)?$/.test(sample)) return true;
  // Multi-value final — both roots of a quadratic, etc. The model routinely
  // emits "x = 2 or x = -2" (often with each term wrapped in $...$) as the
  // final answer. Without this it falls through every other detector (the
  // bare-expression charset below excludes `=`, and the `$` chars fail the
  // algebra-line charset) and lands on the fallback CodeBlock "copy box"
  // with raw $ signs and a Copy button — which is not how a final answer
  // should render. Strip embedded $...$ wraps first, then match 2+ solutions
  // joined by "or" / "and" / ",".
  const stripped = stripEmbeddedDollarWraps(sample);
  if (
    /^[a-zA-Z]\s*=\s*[±+\-]?\d+(?:[.,]\d+)?(?:\s*(?:or|and|,)\s*[a-zA-Z]\s*=\s*[±+\-]?\d+(?:[.,]\d+)?)+$/.test(
      stripped,
    )
  ) {
    return true;
  }
  // Bare simplified expression, no "=" — a final result like "2c^2",
  // "x^2 - 4", "\frac{1}{2}", "√2" rather than a full equation/step.
  if (
    MATH_ANSWER_CHARS_RE.test(sample) &&
    /[\d^√±\\]/.test(sample) &&
    !TWO_WORDS_RE.test(sample)
  ) {
    return true;
  }
  return false;
}

/** Explicit ```answer / ```result fences for a final numeric / math answer. */
export function isAnswerLang(lang: string): boolean {
  return fenceIdForLang(lang) === "answer";
}

/** Any non-prose fence language tag (python, js, …) → always a code block. */
export function isExplicitCodeLang(lang: string): boolean {
  // The exclusion list lives in lib/fenceRegistry.ts (`neverCodeBlock`) so it
  // cannot drift from the structured-fence list again.
  return !isPlainTextFenceLang(lang) && !isNeverCodeBlockLang(lang);
}

/** A copy card: text a tagged fence holds to send as it is. An untagged fence is never one. */
export function shouldRenderAsCopyBlock(
  lang: string,
  content: string,
): boolean {
  if (!isSendableFenceLang(lang)) return false;
  if (looksLikeMathAnswer(content)) return false;
  if (looksLikeFailedDiagram(content)) return false;
  return looksLikeExplicitDraftContent(content);
}

/** The i18n key of a copy card's label: an email, a message, or a plain draft. */
export function copyBlockLabelKey(lang: string): string {
  switch (fenceIdForLang(lang)) {
    case "email":
      return "rich.email_draft";
    case "message":
      return "rich.message_draft";
    default:
      return "rich.copy_draft";
  }
}

/** Cleaned full message for copy. EmailCard has its own copy control. */
export function extractPrimaryCopyText(content: string): string {
  return markdownToCopyText(content);
}
