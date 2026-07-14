import { looksLikeMathFenceBody } from "@/lib/mathFenceRetag";

const COPY_BLOCK_RE =
  /```(?:copy|text|message|email|sms|reply)\n([\s\S]*?)```/i;

export const COPY_LANGS = new Set([
  "copy",
  "text",
  "message",
  "email",
  "sms",
  "reply",
]);

export function isCopyLang(lang: string): boolean {
  return COPY_LANGS.has(lang.trim().toLowerCase());
}

/** Fences with no real language tag — usually plain text from the model. */
export function isProseLang(lang: string): boolean {
  const l = lang.trim().toLowerCase();
  return !l || l === "clike" || l === "text" || l === "plain";
}

/** Heuristic: content is source code, not copy-ready prose. */
export function looksLikeCode(content: string): boolean {
  if (looksLikeExplanatoryProse(content)) return false;
  if (looksLikeMathFenceBody(content)) return false;
  const sample = content.slice(0, 2000);
  if (
    /^\s*(def |class |function |import |export |const |let |var |public |private |protected |#include |package |func |fn |interface |type |enum |struct |impl |module |namespace |using |SELECT |CREATE |INSERT |UPDATE |DELETE |<!DOCTYPE|<\/?[a-z][\w-]*[\s/>])/im.test(
      sample,
    )
  ) {
    return true;
  }
  if (/^\s{4}\S/m.test(sample) || /^\t+\S/m.test(sample)) return true;
  if (/^\s*[\[{]/.test(sample) && /[;\}\],]/.test(sample)) return true;
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
  if (
    /\w+\s*\([^)]*\)\s*[;{]?/m.test(sample) &&
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
  if (looksLikeAssistantMeta(content)) return false;
  if (looksLikeExplanatoryProse(content)) return false;
  const l = lang.trim().toLowerCase();
  if (
    (l === "copy" ||
      l === "message" ||
      l === "email" ||
      l === "sms" ||
      l === "reply") &&
    !looksLikeCode(content)
  ) {
    return false;
  }
  if (isExplicitCodeLang(lang)) return true;
  return looksLikeCode(content);
}

/** Educational / explanatory prose — not a copy-and-send deliverable. */
export function looksLikeExplanatoryProse(content: string): boolean {
  const sample = content.slice(0, 1600).trim();
  if (/^\s*>/m.test(sample)) return true;
  if (/^#{1,6}\s/m.test(sample)) return true;
  if (looksLikeAdvisoryNote(content)) return true;
  if (
    /\*\*[^*]+\*\*/.test(sample) &&
    /(?:in Python|in JavaScript|in TypeScript|these methods|this method|does not modify|do not modify|creates? a new|returns? a new|the following|for example|Note that|Remember that|Keep in mind|are immutable|is immutable)/i.test(
      sample,
    )
  ) {
    return true;
  }
  if (
    /^[-*•]\s/m.test(sample) &&
    sample.split("\n").filter((l) => /^[-*•]\s/.test(l.trim())).length >= 2
  ) {
    return true;
  }
  return false;
}

/** Recommendations, comparisons, career/stack advice — not paste-and-send text. */
export function looksLikeAdvisoryNote(content: string): boolean {
  const sample = content.slice(0, 1600).trim();
  if (
    /^(As a|If you('| a)re|For most|In general|When (choosing|building|learning)|I('| would) (recommend|suggest)|A solid|Good choices|Consider|You might|You('ll| will) (want|find)|Overall,|In practice,)/i.test(
      sample,
    )
  ) {
    return true;
  }
  if (
    /\b(is|are) a (solid|good|great|strong|reasonable|sensible|practical) (choice|combo|option|stack|pick|approach|fit|set)\b/i.test(
      sample,
    )
  ) {
    return true;
  }
  if (
    /\bfor (prototyping|production|enterprise|performance|learning|beginners|most (cases|projects|teams)|day-to-day)\b/i.test(
      sample,
    )
  ) {
    return true;
  }
  if (
    /\b(Python|JavaScript|Java|C\+\+|Rust|Go|TypeScript|Kotlin|Ruby|Swift)\b[\s\S]{0,200}\b(Python|JavaScript|Java|C\+\+|Rust|Go|TypeScript|Kotlin|Ruby|Swift)\b/i.test(
      sample,
    )
  ) {
    return true;
  }
  if (
    sample.length > 100 &&
    !emailDraftSignals(content) &&
    !directMessageSignals(content)
  ) {
    return true;
  }
  return false;
}

/** Regex-only — safe to call from advisory/deliverable checks (no mutual recursion). */
function emailDraftSignals(content: string): boolean {
  const sample = content.trim();
  if (/^(To:|Subject:)/im.test(sample)) return true;
  if (
    /^(Hi|Hello|Dear|Hey)\b/im.test(sample) &&
    /\b(Best|Thanks|Regards|Sincerely|Cheers),/im.test(sample)
  ) {
    return true;
  }
  if (
    /^(Hi|Hello|Dear)\b/im.test(sample) &&
    sample.split("\n").filter((l) => l.trim()).length >= 3
  ) {
    return true;
  }
  return false;
}

function looksLikeEmailDraft(content: string): boolean {
  return emailDraftSignals(content);
}

/** Regex-only — must not call looksLikeAdvisoryNote (was causing stack overflow). */
function directMessageSignals(content: string): boolean {
  const sample = content.trim();
  const words = sample.split(/\s+/).length;
  if (words > 90) return false;
  if (
    /^(please |reminder:|don'?t forget|running late|see you|thanks for|hey |hi )/i.test(
      sample,
    )
  ) {
    return true;
  }
  if (
    words <= 70 &&
    /\b(I'll|I'm|we're|you're|your|let me know)\b/i.test(sample) &&
    !/\b(is a solid|for prototyping|software engineer)\b/i.test(sample)
  ) {
    return true;
  }
  return false;
}

function looksLikeDirectMessage(content: string): boolean {
  return directMessageSignals(content);
}

/** Paste-and-send wording only — not code, notes, or assistant commentary. */
export function looksLikeSendDeliverable(content: string): boolean {
  if (looksLikeCode(content)) return false;
  if (looksLikeAssistantMeta(content)) return false;
  if (looksLikeExplanatoryProse(content)) return false;
  const sample = content.trim();
  if (/^\s*[>#]/.test(sample)) return false;
  if (/^#{1,6}\s/m.test(sample)) return false;
  return looksLikeEmailDraft(content) || looksLikeDirectMessage(content);
}

/** True when content reads like plain prose (not code). */
export function looksLikeProse(content: string): boolean {
  if (looksLikeCode(content)) return false;
  const sample = content.slice(0, 600);
  if (
    /^\s*(def |function |class |import |const |let |var |SELECT |#include |package )/im.test(
      sample,
    )
  ) {
    return false;
  }
  if (/^\s*[\[{<]/m.test(sample) && /[;\}]/.test(sample)) return false;
  return true;
}

/** Assistant follow-up / disclaimer — not something the user would copy and send. */
export function looksLikeAssistantMeta(content: string): boolean {
  const sample = content.slice(0, 800).trim();
  if (
    /^(I (used|assumed|went with|inferred|based|picked|chose|included)|Based on your (answer|response|input|reply)|If you('d| would) prefer|just tell me (and )?I('ll| will)|let me know if|double-check|feel free to (ask|tell)|happy to (revise|update|adjust)|I can (revise|update|adjust)|Note:|Also, (double-check|if ))/i.test(
      sample,
    )
  ) {
    return true;
  }
  if (/\bI assumed\b/i.test(sample) && /\blet me know\b/i.test(sample))
    return true;
  // Math fence validation failures — never a paste-and-send Copy template.
  if (/^(Could not render that diagram\.?|Invalid (graph|geometry) block)/i.test(sample)) {
    return true;
  }
  return false;
}

/** Fences that should render as normal body text — not CopyBlock or CodeBlock. */
export function shouldRenderAsPlainProseFence(
  lang: string,
  content: string,
): boolean {
  if (looksLikeExplanatoryProse(content)) return true;
  if (looksLikeAssistantMeta(content)) return true;
  if (looksLikeCode(content)) return false;
  if (isExplicitCodeLang(lang)) return false;
  const l = lang.trim().toLowerCase();
  if (isCopyLang(l) || isProseLang(lang)) {
    return looksLikeProse(content) && !looksLikeSendDeliverable(content);
  }
  return false;
}

/** Short numeric / boxed math final answer — show as AnswerBlock, never Copy. */
export function looksLikeMathAnswer(content: string): boolean {
  const sample = content.trim();
  if (!sample || sample.length > 160) return false;
  if (sample.split("\n").filter((l) => l.trim()).length > 2) return false;
  // Bare number, optional % / factorial: 120, 5!, -3.5
  if (/^[±+\-]?\d+(?:[.,]\d+)?(?:\s*[%])?!?$/.test(sample)) return true;
  if (/^\$[^$\n]+\$$/.test(sample)) return true;
  if (/^\\boxed\{[^}]+\}$/.test(sample)) return true;
  // Short equation / factorial definition: 0! = 1, x = 3, n! = n × (n-1)!
  if (
    /=/.test(sample) &&
    /^[\da-zA-Z+\-*/^=(){}\\_!\s.$,²³√±×÷·⋅→←↔⇒⇔∞πθ∑∏]+$/.test(sample)
  ) {
    return true;
  }
  return false;
}

/** Explicit ```answer / ```result fences for a final numeric / math answer. */
export function isAnswerLang(lang: string): boolean {
  const l = lang.trim().toLowerCase();
  return l === "answer" || l === "result" || l === "final";
}

/** Any non-prose fence language tag (python, js, …) → always a code block. */
export function isExplicitCodeLang(lang: string): boolean {
  const l = lang.trim().toLowerCase();
  if (!l) return false;
  if (
    l === "copy" ||
    l === "message" ||
    l === "email" ||
    l === "sms" ||
    l === "reply" ||
    l === "clock" ||
    l === "time" ||
    l === "sources" ||
    l === "places" ||
    l === "graph" ||
    l === "geometry" ||
    l === "math" ||
    isAnswerLang(l)
  )
    return false;
  return !isProseLang(l);
}

export function shouldRenderAsCopyBlock(
  lang: string,
  content: string,
): boolean {
  if (looksLikeCode(content)) return false;
  if (looksLikeAssistantMeta(content)) return false;
  if (looksLikeExplanatoryProse(content)) return false;
  if (looksLikeMathAnswer(content)) return false;
  if (isAnswerLang(lang)) return false;
  if (isExplicitCodeLang(lang)) return false;
  const l = lang.trim().toLowerCase();
  if (
    l === "copy" ||
    l === "text" ||
    l === "message" ||
    l === "email" ||
    l === "sms" ||
    l === "reply"
  ) {
    return looksLikeSendDeliverable(content);
  }
  return (
    isProseLang(lang) &&
    looksLikeProse(content) &&
    looksLikeSendDeliverable(content)
  );
}

export function copyBlockLabel(lang: string): string | undefined {
  switch (lang.trim().toLowerCase()) {
    case "email":
      return "Email draft";
    case "sms":
    case "message":
      return "Message draft";
    default:
      return undefined;
  }
}

/** First send-ready block, or the full message when none is marked. */
export function extractPrimaryCopyText(content: string): string {
  const re = /```(?:copy|text|message|email|sms|reply)\n([\s\S]*?)```/gi;
  let match: RegExpExecArray | null;
  while ((match = re.exec(content)) !== null) {
    const body = match[1].trim();
    if (looksLikeSendDeliverable(body)) return body;
  }
  return content.trim();
}

export function hasCopyBlock(content: string): boolean {
  return COPY_BLOCK_RE.test(content);
}
