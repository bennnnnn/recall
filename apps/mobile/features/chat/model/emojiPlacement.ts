/**
 * The user's emoji setting applied to a reply while it streams: the twin of the
 * server's finalize pass (`apps/api/app/modules/chat/emoji_placement.py`).
 *
 * The server keeps the setting on the saved reply ("A few": one emoji leads a heading
 * or label, none in a sentence). Applied only there, a "Hey bini 👋" streamed with its
 * wave and lost it when the saved reply replaced the draft. Both sides read the same
 * cases (`docs/fixtures/emoji_placement_cases.json`), so the draft is already the
 * reply that will be saved.
 */
import { fencedLines } from "@/lib/mdFenceScan";
import { normalizeEmojiUse } from "@/lib/responseTone";

// The server's `prompt_constants.routing.EMOJI` (emoji, flags and their joiners), as
// surrogate pairs: Metro's Babel rewrites a `u`-flag class of astral ranges, and the
// rewritten pattern matched nothing.
const EMOJI_UNIT =
  "\\uD83C[\\uDDE6-\\uDDFF\\uDF00-\\uDFFF]|\\uD83D[\\uDC00-\\uDFFF]|\\uD83E[\\uDC00-\\uDEFF]" +
  "|[\\u2600-\\u27BF\\u2B00-\\u2BFF\\uFE0F\\u200D]";
const EMOJI = new RegExp(`(?:${EMOJI_UNIT})+`);
const EMOJI_ALL = new RegExp(`(?:${EMOJI_UNIT})+`, "g");
// An emoji with the spaces after it: "🧠 Brain" leaves "Brain", "**🧠 Brain**" "**Brain**".
const EMOJI_AND_SPACE = new RegExp(`(?:${EMOJI_UNIT})+[ \\t]*`, "g");
// A space left before a closing bold marker ("**Brain power **") or punctuation.
const SPACE_BEFORE_CLOSE = /[ \t]+(\*\*|__)(?=[\s.,;:!?)]|$)|[ \t]+(?=[.,;:!?)])/g;
// A heading, a list item or a bold label paragraph: its marker, then what it leads.
const LABELLED = /^(\s*(?:#{1,6}\s+|(?:[-*+]|\d{1,3}[.)])\s+)?)(.*)$/;
const BOLD_START = /^(?:\*\*|__)/;
const INLINE_CODE = /(`+)[^`]*?\1/g;
// "### Lesson 2: Loops": a lesson keeps the emoji its own rules give it.
const LESSON = /^#{1,6}\s.*\bLesson\s+\d/m;

function outsideCode(text: string, change: (part: string) => string): string {
  let out = "";
  let last = 0;
  for (const span of text.matchAll(INLINE_CODE)) {
    const start = span.index ?? 0;
    out += change(text.slice(last, start)) + span[0];
    last = start + span[0].length;
  }
  return out + change(text.slice(last));
}

// An emoji used as a sentence break: "Hey bini 👋 How's it going?" lost its 👋 and read
// "Hey bini How's it going?". Between a word and a capitalised word it becomes a full
// stop, unless the word leads into the next ("to 🇫🇷 France") or it is a flag.
const LEADS_ON = new Set([
  "to", "in", "at", "on", "of", "from", "for", "with", "by", "about", "like", "the",
  "a", "an", "my", "your", "our", "their", "his", "her", "its", "and", "or", "i",
]);
const FLAG = /\uD83C[\uDDE6-\uDDFF]/;
const LAST_WORD = /([A-Za-z0-9\u00C0-\u024F']+)[ \t]*$/;
const NEXT_WORD = /^[A-Z][a-z']/;

function dropEmoji(part: string): string {
  let out = "";
  let last = 0;
  for (const match of part.matchAll(EMOJI_AND_SPACE)) {
    const start = match.index ?? 0;
    const before = out + part.slice(last, start);
    const word = LAST_WORD.exec(before);
    const end = start + match[0].length;
    const breaks =
      word !== null &&
      !LEADS_ON.has((word[1] ?? "").toLowerCase()) &&
      !FLAG.test(match[0]) &&
      NEXT_WORD.test(part.slice(end));
    out = breaks ? `${before.replace(/[ \t]+$/, "")}. ` : before;
    last = end;
  }
  return out + part.slice(last);
}

function withoutEmoji(line: string): string {
  const indent = line.slice(0, line.length - line.trimStart().length);
  const body = outsideCode(line.slice(indent.length), dropEmoji)
    .replace(SPACE_BEFORE_CLOSE, (_match, marker: string | undefined) => marker ?? "");
  return `${indent}${body}`.trimEnd();
}

function firstEmoji(text: string): string | null {
  const runs = text.replace(INLINE_CODE, " ").match(EMOJI_ALL) ?? [];
  return runs.find((run) => run.replace(/[\uFE0F\u200D]/g, "") !== "") ?? null;
}

function leadingEmoji(line: string): string {
  const match = LABELLED.exec(line);
  if (!match) return withoutEmoji(line);
  const lead = match[1] ?? "";
  const body = match[2] ?? "";
  const labelled = lead.trim() !== "" || BOLD_START.test(body);
  const emoji = firstEmoji(body);
  if (!labelled || emoji === null) return withoutEmoji(line);
  const rest = withoutEmoji(body);
  return rest ? `${lead}${emoji} ${rest}` : line;
}

/** `text` with its emoji where `level` puts them (the server's `place_emoji`). */
export function placeEmoji(text: string, level: string | null | undefined, userWroteEmoji: boolean): string {
  const use = normalizeEmojiUse(level);
  if (use === "more" || (use === "off" && userWroteEmoji) || !EMOJI.test(text)) return text;
  if (use === "some" && LESSON.test(text)) return text;
  const fenced = fencedLines(text);
  return text
    .split("\n")
    .map((line, index) => {
      if (fenced[index] || line.trimStart().startsWith("|") || !EMOJI.test(line)) return line;
      return use === "off" ? withoutEmoji(line) : leadingEmoji(line);
    })
    .join("\n");
}

/** The streaming draft as the saved reply will read, for the user who asked `priorUserText`. */
export function placeLiveEmoji(
  content: string | undefined,
  level: string | null | undefined,
  priorUserText: string | null,
): string | undefined {
  if (!content) return content;
  return placeEmoji(content, level, EMOJI.test(priorUserText ?? ""));
}
