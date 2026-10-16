/**
 * Detect reference-photo *lookup* intent from plain composer text — mirrors
 * apps/api/app/modules/images/lookup_intent.py (shared cases:
 * docs/fixtures/image_intent_cases.json). Separate from
 * imageGenIntent.ts (creative generation): "show me an ear" / "what does a
 * golden retriever look like" want a real photo, sent as a normal chat turn
 * so the backend's image_search tool/intercept can attach one — not routed
 * into the generate-image flow.
 *
 * Checked before extractImageGenPrompt in useChatSend so this phrasing no
 * longer gets mis-parsed by generation's bare colloquial fallback (the
 * "show me a picture of X" bug).
 */

import { NON_IMAGE_WORDS as GEN_NON_IMAGE_WORDS } from "@/features/images/model/imageGenIntentWords";

const ARTICLES = new Set(["a", "an", "the"]);
const POSSESSIVES = new Set(["my", "your", "our", "his", "her", "their", "its"]);
const REFERENCE_NOUNS = new Set(["picture", "pictures", "photo", "photos", "image", "images", "pic", "pics"]);
// "show me her image", "a photo of him": someone named earlier in the chat.
// "my" / "your" / "our" stay out — "show me my notes" is app content.
const THIRD_PERSON_POSSESSIVES = new Set(["his", "her", "their", "its"]);
const OBJECT_PRONOUNS = new Set(["her", "him", "them", "it"]);
// "can you show me…", "please show me…" ask the same thing as "show me…".
const POLITE_LEADS: string[][] = [
  ["can", "you"], ["could", "you"], ["would", "you"], ["will", "you"], ["can", "u"],
  ["please"], ["pls"], ["just"],
];
// "can I see X", "I want to see X" ask what "let me see X" asks.
const SEE_LEADS: string[][] = [
  ["let", "me", "see"], ["lemme", "see"], ["can", "i", "see"], ["could", "i", "see"],
  ["may", "i", "see"], ["i", "want", "to", "see"], ["i'd", "like", "to", "see"],
  ["i", "would", "like", "to", "see"], ["i", "wanna", "see"],
];
// "send me a photo of X": these verbs need the photo noun, or "find me a
// restaurant" and "give me a list" would turn into photo searches.
const PHOTO_FETCH_VERBS = new Set(["send", "find", "get", "give", "pull", "bring"]);

// "show me my todos", "show me the code": generation's denylist (code, writing,
// app content) plus the maths, chemistry, plan and explanation nouns that
// "show me" / "what does X look like" ask for outside of visual identification.
const LOOKUP_ONLY_NON_IMAGE_WORDS = [
  "deck", "decks", "settings", "profile", "subscription", "history", "progress",
  "streak", "streaks", "score", "scores", "result", "results", "answer", "answers",
  "step", "steps",
  "math", "maths", "arithmetic", "algebra", "algebraic", "calculus",
  "addition", "add", "subtraction", "subtract", "multiplication", "multiply",
  "division", "divide", "sum", "difference", "product", "quotient",
  "remainder", "divisor", "dividend", "fraction", "fractions", "numerator",
  "denominator", "polynomial", "polynomials", "inequality", "inequalities",
  "derivative", "derivatives", "integral", "integrals",
  "graph", "graphs", "chart", "charts", "diagram", "diagrams",
  "flowchart", "flowcharts", "formula", "formulas", "calculation", "calculations",
  "translation", "definition", "meaning", "transcript", "attachment",
  "attachments", "document", "documents", "pdf", "explanation", "breakdown",
  "method", "methods", "working", "workings", "derivation",
  // Chemistry / verified geometry — not stock photos.
  "structure", "structures", "molecule", "molecules", "molecular",
  "compound", "compounds", "chemistry", "chemical", "smiles", "atom", "atoms",
  "bond", "bonds", "triangle", "triangles", "square", "squares", "circle",
  "circles", "rectangle", "rectangles", "geometry", "geometric",
  // Plans and choices — "what does a typical day in Tokyo look like".
  "day", "days", "week", "weekend", "budget", "option",
  "options", "choices", "menu", "menus", "route", "routes", "directions",
  "price", "prices", "cost", "costs", "timeline", "agenda",
  // "Show me some love", "show me some support": not a photo.
  "love", "support", "respect", "kindness", "appreciation", "mercy",
  // Curves the app draws as a graph: "what does a sine wave look like".
  "sine", "cosine", "parabola", "parabolas", "hyperbola", "asymptote",
  "exponential", "logarithmic",
];
// Code or writing nouns that also name a thing to see; they block alone or beside a code word.
const DUAL_USE_WORDS = new Set([
  "bug", "bugs", "branch", "hook", "test", "story", "stage", "phase", "phases",
  "opening", "screen", "button",
]);
// A code word beside a dual-use word keeps it code: "git branch", "custom hook", "unit test".
const CODE_CONTEXT_WORDS = new Set([
  "git", "react", "custom", "unit", "integration", "e2e", "failing", "merge", "feature",
  "submit", "signup", "ui",
]);
const NON_IMAGE_WORDS = new Set(
  [...GEN_NON_IMAGE_WORDS, ...LOOKUP_ONLY_NON_IMAGE_WORDS].filter((word) => !DUAL_USE_WORDS.has(word)),
);

const DEICTICS = new Set(["that", "this", "these", "those"]);
const PHOTO_ADJECTIVES = new Set(["real", "actual", "nice", "good", "clear"]);
const REASON_CLAUSE = /,\s*(?:i|i'm|im|so|because|since|for|to)\b/i;
const NOT_A_NOUN = new Set(["again", "but", "one", "part", "bit", "more", "in", "with", "please"]);

const EXPLANATION_CUES = new Set([
  "how", "why", "when", "where", "what", "solve", "explain", "prove",
  "calculate", "compute", "work", "works", "mean", "means", "becoming",
]);

const MAX_SUBJECT_WORDS = 8;

const EDGE_PUNCT = /^[.,!?;:"'()[\]]+|[.,!?;:"'()[\]]+$/g;

function foldToken(word: string): string {
  return word.toLowerCase().replace(EDGE_PUNCT, "");
}

function tokens(text: string): string[] {
  return text.split(/\s+/).filter(Boolean);
}

function referenceSubject(toks: string[]): string | null {
  const folded = toks.map(foldToken);
  if (!folded.length) return null;
  if (folded.length === 1 && OBJECT_PRONOUNS.has(folded[0])) return folded[0];
  if (folded.length === 2 && THIRD_PERSON_POSSESSIVES.has(folded[0]) && REFERENCE_NOUNS.has(folded[1])) {
    return folded[0];
  }
  return null;
}

function cleanSubject(raw: string): string | null {
  // "a habesha kemis, i want to describe it in my caption": the reason is not the subject.
  const reason = REASON_CLAUSE.exec(raw);
  const kept = reason ? raw.slice(0, reason.index) : raw;
  const subject = kept.trim().replace(/[.!?]+$/g, "").trim();
  if (!subject || subject.length < 2) return null;
  if (
    ["×", "÷", "=", "^"].some((symbol) => subject.includes(symbol)) ||
    [" + ", " - ", " / ", " * ", " − "].some((operator) => subject.includes(operator))
  ) return null;
  const words = subject.split(/\s+/);
  if (!words.length || words.length > MAX_SUBJECT_WORDS) return null;
  const folded = words.map(foldToken);
  if (!folded[0] || POSSESSIVES.has(folded[0])) return null;
  // "Show me that again but simpler" asks to repeat an answer.
  if (DEICTICS.has(folded[0]) && folded.length > 1 && NOT_A_NOUN.has(folded[1])) return null;
  if (folded.some((w) => NON_IMAGE_WORDS.has(w) || EXPLANATION_CUES.has(w))) return null;
  // "show me the bug (again)" is about code; "show me a bed bug" wants a photo.
  if (DUAL_USE_WORDS.has(folded[0]) && folded.slice(1).every((w) => NOT_A_NOUN.has(w))) return null;
  // "show me the git branch" is about code; "show me the main stage" wants a photo.
  const pairs = folded.slice(1).map((w, i) => [folded[i], w]);
  const isCodePair = (pair: string[]) =>
    pair.some((w) => DUAL_USE_WORDS.has(w)) && pair.some((w) => CODE_CONTEXT_WORDS.has(w));
  if (pairs.some(isCodePair)) return null;
  return subject;
}

function stripLeadingArticle(toks: string[]): string[] {
  return toks.length && ARTICLES.has(toks[0].toLowerCase()) ? toks.slice(1) : toks;
}

function stripReferenceNounPrefix(toks: string[]): string[] {
  let i = 0;
  if (i < toks.length && ARTICLES.has(toks[i].toLowerCase())) i += 1;
  // "a real photo of", "an actual picture of"
  if (
    i + 1 < toks.length &&
    PHOTO_ADJECTIVES.has(toks[i].toLowerCase()) &&
    REFERENCE_NOUNS.has(toks[i + 1].toLowerCase())
  ) {
    i += 1;
  }
  if (i < toks.length && REFERENCE_NOUNS.has(toks[i].toLowerCase())) {
    i += 1;
    if (i < toks.length && toks[i].toLowerCase() === "of") i += 1;
    return toks.slice(i);
  }
  return toks;
}

function startsWith(folded: string[], lead: string[]): boolean {
  return folded.length > lead.length && lead.every((word, i) => folded[i] === word);
}

function stripPoliteLead(toks: string[]): string[] {
  let changed = true;
  while (changed) {
    changed = false;
    const folded = toks.map((t) => t.toLowerCase());
    for (const lead of POLITE_LEADS) {
      if (startsWith(folded, lead)) {
        toks = toks.slice(lead.length);
        changed = true;
        break;
      }
    }
  }
  return toks;
}

/** SUBJECT from "[a/an/the]? [picture/photo/image of]? SUBJECT". */
function photoSubject(toks: string[]): string | null {
  let remaining = stripLeadingArticle(toks);
  remaining = stripReferenceNounPrefix(remaining);
  remaining = stripLeadingArticle(remaining);
  if (!remaining.length) return null;
  return referenceSubject(remaining) ?? cleanSubject(remaining.join(" "));
}

function matchShowMe(toks: string[]): string | null {
  if (toks.length < 2 || toks[0].toLowerCase() !== "show") return null;
  let i = 1;
  if (i < toks.length && toks[i].toLowerCase() === "me") i += 1;
  return photoSubject(toks.slice(i));
}

function matchLetMeSee(toks: string[]): string | null {
  const folded = toks.map((t) => t.toLowerCase());
  for (const lead of SEE_LEADS) {
    if (startsWith(folded, lead)) return photoSubject(toks.slice(lead.length));
  }
  return null;
}

/** "send / find / get me a photo of SUBJECT", "pull up a picture of SUBJECT" */
function matchFetchPhoto(toks: string[]): string | null {
  if (toks.length < 3 || !PHOTO_FETCH_VERBS.has(toks[0].toLowerCase())) return null;
  let i = 1;
  if (i < toks.length && toks[i].toLowerCase() === "up") i += 1;
  if (i < toks.length && toks[i].toLowerCase() === "me") i += 1;
  let rest = stripLeadingArticle(toks.slice(i));
  if (rest.length && rest[0].toLowerCase() === "some") rest = rest.slice(1);
  if (!rest.length || !REFERENCE_NOUNS.has(rest[0].toLowerCase())) return null;
  return photoSubject(rest);
}

/** "show me what SUBJECT looks like" */
function matchShowWhatLooksLike(toks: string[]): string | null {
  if (toks.length < 5 || toks[0].toLowerCase() !== "show") return null;
  let i = 1;
  if (toks[i].toLowerCase() === "me") i += 1;
  if (i >= toks.length || toks[i].toLowerCase() !== "what") return null;
  const last = toks[toks.length - 1].toLowerCase().replace(/[?.!]+$/g, "");
  if (last !== "like" || !["looks", "look"].includes(toks[toks.length - 2].toLowerCase())) return null;
  const subjectTokens = stripLeadingArticle(toks.slice(i + 1, -2));
  if (!subjectTokens.length) return null;
  return cleanSubject(subjectTokens.join(" "));
}

function matchLookLike(toks: string[]): string | null {
  if (toks.length < 5 || toks[0].toLowerCase() !== "what") return null;
  if (!["does", "do"].includes(toks[1].toLowerCase())) return null;
  const last = toks[toks.length - 1].toLowerCase().replace(/[?.!]+$/g, "");
  const secondLast = toks[toks.length - 2].toLowerCase();
  if (last !== "like" || secondLast !== "look") return null;
  const subjectTokens = stripLeadingArticle(toks.slice(2, -2));
  if (!subjectTokens.length) return null;
  return cleanSubject(subjectTokens.join(" "));
}

/** Return the reference-photo subject if `text` clearly wants a real photo, else null. */
export function extractImageLookupQuery(text: string): string | null {
  const trimmed = text.trim();
  if (!trimmed || trimmed.length > 200) return null;

  let toks = stripPoliteLead(tokens(trimmed));
  // "what does a gelada look like 🐒": a trailing emoji is not part of the ask.
  while (toks.length && !/[\p{L}\p{N}]/u.test(toks[toks.length - 1])) toks = toks.slice(0, -1);
  if (!toks.length) return null;

  return (
    matchShowWhatLooksLike(toks) ??
    matchShowMe(toks) ??
    matchLetMeSee(toks) ??
    matchFetchPhoto(toks) ??
    matchLookLike(toks)
  );
}
