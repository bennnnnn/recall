/**
 * The one worked-solution layout the API writes for every subject:
 * **Given**, **Find**, **Formula**, **Substitution** or **Steps**, **Answer**,
 * each a bold heading on its own line followed by one state per line, with
 * the move as a short note after " — " (`$2x = 8$ — subtract 3`).
 */
const WORKOUT_HEADINGS: ReadonlySet<string> = new Set([
  "Given",
  "Find",
  "Formula",
  "Substitution",
  "Steps",
  "Answer",
]);

/** A heading as written, with an optional trailing colon. */
export function workoutHeading(text: string): string | null {
  const heading = text.trim().replace(/:$/, "");
  return WORKOUT_HEADINGS.has(heading) ? heading : null;
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

