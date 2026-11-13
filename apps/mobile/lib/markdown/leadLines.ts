/**
 * Lines that each open with a bold lead stay separate lines.
 *
 * A model lists options one per line with single breaks ("🇨🇭 **Switzerland — best for
 * quality of life** (…)", then "🇩🇪 **Germany — …**"), and Markdown joins single breaks
 * into one paragraph, so the options ran together. A run of two or more such lines
 * becomes one paragraph each. A lead may follow emoji or flags; list items, headings,
 * quotes, tables and indented lines are left alone (twin:
 * apps/api/app/modules/chat/lead_lines.py).
 *
 * A worked reply's headings start their own paragraph too, whatever line is above them. A
 * model wrote its sections with single breaks ("$3x - 5 < 2x + 4$" then "**Required**"),
 * and the phone showed "3x − 5 < 2x + 4 **Required** Solve for x. **Solution**" on one row
 * (2026-11-13). In a reply that heads a line **Given** or **Required**, a heading is a bold
 * line alone (a section, a formula's name, a part, a bold value) or a section's, a part's or
 * a numbered move's bold title with words after it ("**1. Subtract 2x** — subtraction
 * property"). A bold label in a sentence ("**Speed:** 3 m/s") is the line it is on, and
 * stays.
 */

import { rewriteFenced } from "@/lib/markdown/markdownRegions";
import { isWorkedReply, SOLUTION_HEADING, WORKOUT_HEADINGS } from "@/lib/markdown/workoutSection";

/** What may come before the bold lead: emoji, flags, their modifiers and joiners, spaces. */
const PREFIX = /^[\p{So}\p{Sk}\p{Mn}\p{Cf} ]*$/u;
const MAX_PREFIX = 16;

const BOLD_HEAD = /^\*\*([^*\n]+)\*\*(.*)$/;
const SECTIONS = new Set([...WORKOUT_HEADINGS, SOLUTION_HEADING]);
/** "Answer (a)", "1. Subtract 4", "2) Divide", "(b) Speed", "Part (c): Time", "d) Distance". */
const TITLE =
  /^(?:Answer \([a-h]\)|\d+[.)]\s.*|(?:part\s+\(?[a-h]\)?|\([a-h]\)|[a-h]\))\s*[.:]?\s*\S.*)$/i;

/** `**Lead**` (or `🇨🇭 **Lead**`) at the start of an unindented line. */
function opensWithBoldLead(line: string): boolean {
  const start = line.indexOf("**");
  if (start < 0 || line.startsWith(" ")) return false;
  // Counted in characters, as the API counts them (a flag is two, not four).
  const prefix = line.slice(0, start);
  if (Array.from(prefix).length > MAX_PREFIX || !PREFIX.test(prefix)) return false;
  return line.indexOf("**", start + 2) > start + 2;
}

/** A worked reply's heading: a bold line alone, or a section's, a part's or a numbered
 * move's bold title with words after it. */
function isHeading(line: string): boolean {
  const bold = BOLD_HEAD.exec(line);
  if (!bold) return false;
  const rest = bold[2]!.trim();
  if (rest === "" || rest === ":") return true;
  const title = bold[1]!.trim().replace(/:$/, "").trim();
  return SECTIONS.has(title) || TITLE.test(title);
}

function separate(prose: string, worked: boolean): string {
  const lines = prose.split("\n");
  const out: string[] = [];
  lines.forEach((line, index) => {
    const above = index > 0 ? lines[index - 1]! : "";
    if (
      (opensWithBoldLead(line) && opensWithBoldLead(above)) ||
      (worked && above.trim() && isHeading(line))
    ) {
      out.push("");
    }
    out.push(line);
  });
  return out.join("\n");
}

/**
 * Each line of a run of bold-lead lines, and each heading of a worked reply, becomes its
 * own paragraph. `workedAbove`: the text is a part of a worked reply whose **Given** came
 * before it (a stream's later part).
 */
export function separateLeadLines(text: string, workedAbove = false): string {
  const worked = workedAbove || isWorkedReply(text);
  return rewriteFenced(text, (prose) => separate(prose, worked), () => null);
}
