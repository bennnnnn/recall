import { fencedLines } from "@/lib/fence/scan";

/**
 * What is asked: **Required**, or **Find** in a reply written before November 2026 (and in
 * one a model still heads that way).
 */
const REQUIRED_HEADINGS: readonly string[] = ["Required", "Find"];

/** The headings that open a worked reply, behind a thin rule: what it is given and what is asked. */
export const OPENING_HEADINGS: readonly string[] = ["Given", ...REQUIRED_HEADINGS];

/**
 * The heading alone between what is asked and the working (November 2026): no lines of its
 * own, the sections below it are its lines.
 */
export const SOLUTION_HEADING = "Solution";

/** **Solution** alone on its line, with an optional trailing colon. */
export function isSolutionHeading(text: string): boolean {
  return text.trim().replace(/:$/, "") === SOLUTION_HEADING;
}

/**
 * The one worked-solution layout the API writes for every subject:
 * **Given**, **Required**, **Solution** (alone, `isSolutionHeading`), the formula under
 * its name ("**Average speed formula**", see `lawHeading`; a formula with no name follows
 * **Solution** with no heading of its own since 2026-11-11, **Formula** in older replies),
 * **Substitution** or **Steps**, **Answer** (**Answer (a)** for one part),
 * each a bold heading on its own line followed by one state per line, with
 * the move written as a short note after " — " (`$2x = 8$ — subtract 3`), which the
 * phone draws as a line of its own above that state, never at the right edge. A
 * rearrangement for the unknown is a line of its own (`Solve for $t$`), never a note.
 */
export const WORKOUT_HEADINGS: readonly string[] = [
  ...OPENING_HEADINGS,
  "Formula",
  "Substitution",
  "Steps",
  "Answer",
];

const PART_ANSWER = /^Answer \([a-h]\)$/;

/** A heading as written, with an optional trailing colon. */
export function workoutHeading(text: string): string | null {
  const heading = text.trim().replace(/:$/, "");
  return WORKOUT_HEADINGS.includes(heading) || PART_ANSWER.test(heading) ? heading : null;
}

/** The answer of the whole question, or of one part ("Answer (a)"). */
export function isAnswerHeading(heading: string): boolean {
  return heading === "Answer" || PART_ANSWER.test(heading);
}

/**
 * A formula's own name heads its section ("**Constant acceleration formula**"), so it
 * is no fixed word: in a worked reply, a short bold line alone over a line of maths, or
 * (`underSolution`) right under **Solution** over any line, as a procedure's name heads its
 * rule in words ("**Conservation of atoms and charge**", 2026-11-11).
 */
export function lawHeading(text: string, firstLine: string, underSolution = false): string | null {
  const heading = text.trim();
  if (!heading || /[.:?!]$/.test(heading) || heading.split(/\s+/).length > 10) return null;
  // A numbered move ("1. Subtract 4 from both sides") and a part are their own blocks.
  if (/^\d+[.)]\s/.test(heading) || workoutPart(heading)) return null;
  return underSolution || /^\$/.test(firstLine.trim()) ? heading : null;
}

const WORKED_LINE_RE = new RegExp(String.raw`^\*\*(?:${OPENING_HEADINGS.join("|")}):?\*\*`);

/** A reply worked in sections: it states what it is given or what is asked (a follow-up
 * that changes one given often skips Required). Read over the whole reply, its fences
 * left out: a part after an answer card (`---`, **(b) …**) is as worked as the first. */
export function isWorkedReply(text: string): boolean {
  if (!text.includes("**")) return false;
  const fenced = fencedLines(text, false);
  return text.split("\n").some((line, index) => !fenced[index] && WORKED_LINE_RE.test(line));
}

/** ``$2x = 8$ — subtract 3``: the state, then its move. A dash inside math is the math's. */
export function splitWorkoutNote(line: string): { state: string; note: string | null } {
  let inMath = false;
  for (let i = 0; i < line.length; i += 1) {
    if (line[i] === "$") inMath = !inMath;
    if (!inMath && line.startsWith(" — ", i)) {
      return { state: line.slice(0, i).trim(), note: line.slice(i + 3).trim() || null };
    }
  }
  return { state: line, note: null };
}

// An answer line's maths, a relation inside it or around it, and a word of a sentence.
const MATHS = /\$\$[\s\S]*?\$\$|\$[^$\n]*\$|\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\]/;
const RELATION = /[=≈<>≤≥≠]|\\(?:approx|leq?|geq?|neq?|lt|gt|equiv|sim|propto)(?![A-Za-z])/;
const LONG_WORD = /\p{L}{3,}/gu;

function wordsOutsideMaths(text: string): number {
  return (text.replace(new RegExp(MATHS.source, "g"), " ").match(LONG_WORD) ?? []).length;
}

/**
 * A line an answer's box holds: one that states a value, never a sentence its maths only
 * illustrates. "A line from $(-3, -5)$ to $(3, 7)$ — slope $2$, $y$-intercept $1$." was drawn
 * in the box (2026-11-13). Read by its shape: a sentence has no relation anywhere (`=`, `≈`,
 * `<`, inside the maths or around it), four words or more (of three letters) outside the
 * maths, two of them after the first maths. An equation ("The area is $A = 24$ cm²", "Sum of
 * the angles $= 180°$"), a value with its unit after a lead ("The speed is about $4.2$ m/s")
 * and a short answer in words ("Sodium chloride") are values. Twin: the API's
 * `services/card_text.sentence_answer`, which keeps such a line out of a card.
 */
export function isAnswerValue(line: string): boolean {
  if (RELATION.test(line)) return true;
  const first = MATHS.exec(line);
  const after = first ? line.slice(first.index + first[0].length) : line;
  return wordsOutsideMaths(line) < 4 || wordsOutsideMaths(after) < 2;
}

/**
 * A heading inside Solution, a level under the sections: a formula under its name,
 * Substitution, Steps. Given, Required, Solution and Answer are the sections. Read from
 * the heading alone, so a reply with no **Solution** heading is drawn the same way.
 */
export function isWorkingHeading(heading: string): boolean {
  return (
    !OPENING_HEADINGS.includes(heading) &&
    !isAnswerHeading(heading) &&
    !isSolutionHeading(heading)
  );
}

/** **Required** or an older **Find**: what is asked. */
export function isRequiredHeading(heading: string): boolean {
  return REQUIRED_HEADINGS.includes(heading);
}

/**
 * ``$v$ — speed`` → ``$v$ (speed)``: what is asked reads as one line, the unknown with its
 * meaning beside it in brackets, symbol first as in Given, never a move's note. The API
 * writes it this way since November 2026 (`services/workout.asked_line`); older replies
 * and a model's own reply are drawn the same.
 */
export function askedLine(line: string): string {
  const { state, note } = splitWorkoutNote(line);
  return note ? `${state} (${note})` : state;
}

// "(a) Acceleration", "Part (b): Speed after 3 s", "c) Distance": one part of
// a question in parts, labelled by its letter and what it finds.
const WORKOUT_PART_RE =
  /^(?:part\s+\(?([a-h])\)?|\(([a-h])\)|([a-h])\))\s*[.:]?\s*(?:[—–-]\s*)?(\S.*)$/i;

/** A part label written alone in bold, or null for any other bold line. */
export function workoutPart(text: string): { letter: string; title: string } | null {
  const match = WORKOUT_PART_RE.exec(text.trim());
  if (!match) return null;
  const letter = (match[1] ?? match[2] ?? match[3] ?? "").toLowerCase();
  const title = (match[4] ?? "").trim();
  return letter && title ? { letter, title } : null;
}

