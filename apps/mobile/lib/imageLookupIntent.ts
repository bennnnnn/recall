/**
 * Detect reference-photo *lookup* intent from plain composer text — mirrors
 * apps/api/app/services/image_lookup_intent.py. Separate from
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

// Keep in sync with image_lookup_intent.py's _NON_IMAGE_WORDS.
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
  "graph", "graphs", "chart", "charts", "diagram", "diagrams", "table",
  "tables", "formula", "formulas", "calculation", "calculations",
  "translation", "definition", "meaning", "transcript", "attachment",
  "attachments", "document", "documents", "pdf", "explanation", "breakdown",
  "method", "methods", "working", "workings", "derivation",
  // Chemistry / verified geometry — not stock photos.
  "structure", "structures", "molecule", "molecules", "molecular",
  "compound", "compounds", "chemistry", "chemical", "smiles", "atom", "atoms",
  "bond", "bonds", "triangle", "triangles", "square", "squares", "circle",
  "circles", "rectangle", "rectangles", "geometry", "geometric",
]);

const EXPLANATION_CUES = new Set([
  "how", "why", "when", "where", "what", "solve", "explain", "prove",
  "calculate", "compute", "work", "works", "mean", "means",
]);

const MAX_SUBJECT_WORDS = 8;

function tokens(text: string): string[] {
  return text.split(/\s+/).filter(Boolean);
}

function cleanSubject(raw: string): string | null {
  const subject = raw.trim().replace(/[.!?]+$/g, "").trim();
  if (!subject || subject.length < 2) return null;
  const words = subject.toLowerCase().split(/\s+/);
  if (!words.length || words.length > MAX_SUBJECT_WORDS) return null;
  if (POSSESSIVES.has(words[0])) return null;
  if (words.some((w) => NON_IMAGE_WORDS.has(w) || EXPLANATION_CUES.has(w))) return null;
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

function matchShowMe(toks: string[]): string | null {
  if (toks.length < 2 || toks[0].toLowerCase() !== "show") return null;
  let i = 1;
  if (i < toks.length && toks[i].toLowerCase() === "me") i += 1;
  let remaining = stripLeadingArticle(toks.slice(i));
  remaining = stripReferenceNounPrefix(remaining);
  remaining = stripLeadingArticle(remaining);
  if (!remaining.length) return null;
  return cleanSubject(remaining.join(" "));
}

function matchLetMeSee(toks: string[]): string | null {
  if (toks.length < 4) return null;
  if (toks[0].toLowerCase() !== "let" || toks[1].toLowerCase() !== "me" || toks[2].toLowerCase() !== "see") {
    return null;
  }
  let remaining = stripLeadingArticle(toks.slice(3));
  remaining = stripReferenceNounPrefix(remaining);
  remaining = stripLeadingArticle(remaining);
  if (!remaining.length) return null;
  return cleanSubject(remaining.join(" "));
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

  const toks = tokens(trimmed);
  if (!toks.length) return null;

  return matchShowMe(toks) ?? matchLetMeSee(toks) ?? matchLookLike(toks);
}
