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

// Keep in sync with lookup_intent.py's _NON_IMAGE_WORDS.
const NON_IMAGE_WORDS = new Set([
  "todo", "todos", "task", "tasks", "list", "lists", "reminder", "reminders",
  "project", "projects", "account", "accounts", "script", "scripts", "code",
  "function", "functions", "class", "classes", "file", "files", "folder",
  "folders", "chat", "chats", "note", "notes", "summary", "summaries", "plan",
  "plans", "schedule", "schedules", "event", "events", "meeting", "meetings",
  "quiz", "quizzes", "flashcard", "flashcards", "deck", "decks", "email",
  "emails", "message", "messages", "reply", "replies", "draft", "drafts",
  "report", "reports", "settings", "profile", "subscription", "password",
  "passwords", "history", "progress", "streak", "streaks", "score", "scores",
  "result", "results", "example", "examples", "problem", "problems",
  "equation", "equations", "question", "questions", "exercise", "exercises",
  "homework", "solution", "solutions", "answer", "answers", "proof", "proofs",
  "worksheet", "worksheets", "assignment", "assignments", "step", "steps",
  // How-to / listicle heads — not stock infographics. Do not add "way"
  // (milky way) or "guide" (tour-guide photos).
  "stops", "ways", "tips", "tip", "secrets", "habits", "tricks", "stages",
  "phases",
  "graph", "graphs", "chart", "charts", "diagram", "diagrams",
  "flowchart", "flowcharts",
  "table",
  "tables", "formula", "formulas", "calculation", "calculations",
  "math", "maths", "arithmetic", "algebra", "algebraic", "calculus",
  "addition", "add", "subtraction", "subtract", "multiplication", "multiply",
  "division", "divide", "sum", "difference", "product", "quotient",
  "remainder", "divisor", "dividend", "fraction", "fractions", "numerator",
  "denominator", "polynomial", "polynomials", "inequality", "inequalities",
  "derivative", "derivatives", "integral", "integrals",
  "translation", "definition", "meaning", "transcript", "attachment",
  "attachments", "document", "documents", "pdf", "explanation", "breakdown",
  "method", "methods", "working", "workings", "derivation",
  // Chemistry / verified geometry — not stock photos.
  "structure", "structures", "molecule", "molecules", "molecular",
  "compound", "compounds", "chemistry", "chemical", "smiles", "atom", "atoms",
  "bond", "bonds", "triangle", "triangles", "square", "squares", "circle",
  "circles", "rectangle", "rectangles", "geometry", "geometric",
  // Plans and choices — "what does a typical day in Tokyo look like".
  "day", "days", "week", "weekend", "routine", "budget", "itinerary", "option",
  "options", "choices", "menu", "menus", "route", "routes", "directions",
  "price", "prices", "cost", "costs", "timeline", "agenda",
]);

const DEICTICS = new Set(["that", "this", "these", "those"]);
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
  const subject = raw.trim().replace(/[.!?]+$/g, "").trim();
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
  return subject;
}

function stripLeadingArticle(toks: string[]): string[] {
  return toks.length && ARTICLES.has(toks[0].toLowerCase()) ? toks.slice(1) : toks;
}

function stripReferenceNounPrefix(toks: string[]): string[] {
  let i = 0;
  if (i < toks.length && ARTICLES.has(toks[i].toLowerCase())) i += 1;
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
