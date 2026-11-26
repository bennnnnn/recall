/**
 * The streaming preprocess cuts a reply's closed text into parts and
 * preprocesses each once (lib/markdown/segmentedPreprocess.ts). At every line
 * of every reply here it must give exactly what `preprocessMarkdown` gives the
 * whole stable prefix, as it did before it was cut.
 */
import * as preprocess from "@/lib/markdown/preprocess";
import { preprocessMarkdown } from "@/lib/markdown/preprocess";
import {
  findStableMarkdownPrefixLen,
  preprocessMarkdownForStream,
  preprocessSettledMarkdown,
  type StreamingPreprocessCache,
} from "@/lib/markdown/preprocessStream";
import { presentStreamTail } from "@/lib/markdown/presentation";
import { isWorkedReply } from "@/lib/markdown/workoutSection";
import { formatAssistantMathExpr } from "@/lib/math/formatInput";
import { STREAMING_REPLIES } from "@/lib/__tests__/fixtures/streamingReplies";

import chemistry from "../../../../docs/fixtures/chemistry_replies.json";
import physics from "../../../../docs/fixtures/physics_replies.json";
import presentation from "../../../../docs/fixtures/presentation_cases.json";
import chatCode from "../../../api/app/tests/behavior/sweep_corpus/chat_code.json";
import followups from "../../../api/app/tests/behavior/sweep_corpus/followups.json";
import lifeAdmin from "../../../api/app/tests/behavior/sweep_corpus/life_admin.json";
import mathScience from "../../../api/app/tests/behavior/sweep_corpus/math_science.json";
import wordProblems from "../../../api/app/tests/behavior/sweep_corpus/stem_word_problems.json";
import writing from "../../../api/app/tests/behavior/sweep_corpus/writing.json";

type Reply = [name: string, text: string];

const sweep: Reply[] = [chatCode, followups, lifeAdmin, mathScience, wordProblems, writing]
  .flat()
  .flatMap((turn: { id: string; reply?: string }): Reply[] =>
    typeof turn.reply === "string" ? [[turn.id, turn.reply]] : [],
  );

const F = "```";
/** Fences indented under list items (audit MX-2): a stream cuts after them now. */
const INDENTED_FENCES: Reply[] = [
  ["indented-bash", ["Set it up in three steps.", "",
    ...[1, 2, 3].flatMap((n) => [`${n}. Install part ${n}:`, "", `   ${F}bash`, `   npm install part-${n}`, `   ${F}`, "",
      `   It prints \`part-${n}\` when it is done. Costs $5 a month.`, ""]), "That is all."].join("\n")],
  ["indented-python-maths", ["Here is the plan.", "",
    "1. Write the function:", "", `   ${F}python`, "   def area(r):", "       return 3.14 * r ** 2", `   ${F}`, "",
    "2. The formula is", "", "   $$", "   A = \\pi r^2", "   $$", "",
    "3. Check it:", "", `  ${F}`, "  area(2)", `  ${F}`, "", "   The answer is $12.56$.", "",
    `${F}python`, "print(area(3))", F, "", "Done."].join("\n")],
  ["indented-worked", ["- **Given**", "", `  ${F}math`, "  v = 2", `  ${F}`, "",
    "- **Required**", "", "  $t$", "", "- Solve:", "", `   ${F}answer`, "   t = 5\\,\\mathrm{s}", `   ${F}`, "",
    "So it takes five seconds."].join("\n")],
  ["indented-tilde", ["Two ways:", "", "1. With tildes:", "", "   ~~~js", "   run()", "   ~~~", "",
    "2. With ticks:", "", `   ${F}js`, "   run()", `   ${F}`, "", "**Speed**", "Both run the same."].join("\n")],
  ["interrupted-math", ["Set up:", "```math", "x + 2 = 5", "2. **Simplify:** take 2 away.", "```", "", "Then we check the result.", "", "$$", "x = 3", "$$", ""].join("\n")],
  ["interrupted-indented-math", ["1. **Set up:**", "   ```math", "   x + 2 = 5", "2. **Simplify:** take 2 away.", "   ```", "", "Then we check the result.", "", "$$", "x = 3", "$$", ""].join("\n")],
  // A code fence in a list item inside a worked reply: the parts still preprocess as the whole.
  ["indented-durable-then-given", ["**Speed**", "$v = d / t$", "", "- Code:", "", `  ${F}python`, "  v = d / t", `  ${F}`, "",
    "A paragraph.", "", "**Given**", "$d = 10$", "", "Done."].join("\n")],
  ["indented-durable-between-givens", ["**Given**", "$d = 10$", "", "**Speed**", "$v = d / t$", "", "- Code:", "",
    `  ${F}python`, "  v = d / t", `  ${F}`, "", "A paragraph.", "", "**Required**", "$v$", "", "**Law of speed**", "$v = 5$", "", "Done."].join("\n")],
];

/** An informational reply's nested members (SCAN_LAYOUT): the step repair reads the list
 * open above them across blank lines, so no cut may fall between (review, #2601). */
const SCAN_LAYOUT_LISTS: Reply[] = [
  ["members-after-blank", ["1. **Natural science** — the physical world.", "", "    Its main branches:",
    "    - **Physics**: matter and energy", "    - **Chemistry**: substances", "",
    "2. **Social science** — people.", "", "    - **History**", "    - **Economics**", ""].join("\n")],
  ["members-under-heading", ["## Types of Science", "", "### Natural sciences", "",
    "    - **Physics**: matter", "", "    - **Chemistry**: substances", "", "### Formal sciences", "",
    "    - **Logic**", ""].join("\n")],
  ["three-levels", ["1. **Natural**", "", "    1. **Physics**", "", "        1. Mechanics", "        2. Optics", "",
    "    2. **Chemistry**", "", "2. **Social**", ""].join("\n")],
];

const replies: Reply[] = [
  ...INDENTED_FENCES,
  ...SCAN_LAYOUT_LISTS,
  ...Object.entries(STREAMING_REPLIES),
  ...Object.entries(physics.replies).map(([name, entry]): Reply => [name, entry.reply]),
  ...Object.entries(chemistry.replies).map(([name, entry]): Reply => [name, entry.reply]),
  ...presentation.cases.map((c): Reply => [c.id, c.input]),
  ...sweep,
];

/** Long replies: runs of corpus replies, one after another. */
const longReplies: Reply[] = Array.from({ length: 8 }, (_, i): Reply => {
  const run = sweep.slice(i * 6, i * 6 + 6).map(([, text]) => text);
  return [`run-${i}`, run.join("\n\n")];
});

function lineEnds(text: string): number[] {
  const ends: number[] = [];
  for (let i = text.indexOf("\n"); i >= 0; i = text.indexOf("\n", i + 1)) ends.push(i + 1);
  ends.push(text.length);
  return ends;
}

/** What the stream preprocess gave before it was cut: the whole stable prefix, then the
 * tail, presented under the prefix's last line. */
function wholePrefix(content: string, presented: boolean): string {
  const stable = findStableMarkdownPrefixLen(content);
  const closed = content.slice(0, stable);
  const head = stable > 0
    ? preprocessMarkdown(closed, formatAssistantMathExpr, { presented })
    : "";
  const above = stable > 0 ? (content.slice(0, stable - 1).split("\n").pop() ?? "") : "";
  return head + presentStreamTail(content.slice(stable), presented, isWorkedReply(closed), above);
}

/** Stream `text` a line at a time; the first line where the two differ, or null. */
function firstDifference(text: string, presented = false): string | null {
  let cache: StreamingPreprocessCache | null = null;
  for (const end of lineEnds(text)) {
    const content = text.slice(0, end);
    const streamed = preprocessMarkdownForStream(content, cache, formatAssistantMathExpr, {
      presented,
    });
    cache = streamed.cache;
    if (streamed.prepared !== wholePrefix(content, presented)) return content;
  }
  return null;
}

function partsOf(text: string): number {
  let cache: StreamingPreprocessCache | null = null;
  for (const end of lineEnds(text)) {
    cache = preprocessMarkdownForStream(text.slice(0, end), cache, formatAssistantMathExpr).cache;
  }
  return (cache?.segments?.starts.length ?? 0) + 1;
}

describe("preprocessing a stream in parts", () => {
  it("gives every corpus reply, at every line, what the whole prefix gives", () => {
    const differ = replies.filter(([, text]) => firstDifference(text) !== null).map(([name]) => name);
    expect(differ).toEqual([]);
  });

  it("gives long replies, at every line, what the whole prefix gives", () => {
    const differ = longReplies.filter(([, text]) => firstDifference(text) !== null);
    expect(differ.map(([name]) => name)).toEqual([]);
  });

  it("gives a saved row held in stream layout what the whole prefix gives", () => {
    for (const [name, text] of Object.entries(STREAMING_REPLIES)) {
      expect({ name, at: firstDifference(text, true) }).toEqual({ name, at: null });
    }
  });

  it("reads a worked region again when its Given label arrives after a bold label", () => {
    const text = [
      "Here is the working.",
      "",
      "**Speed**",
      "$v = d / t$",
      "",
      "A paragraph between the two.",
      "",
      "**Given**",
      "$d = 10$",
      "",
      "**Required**",
      "$v$",
      "",
      "Done.",
      "",
    ].join("\n");
    expect(firstDifference(text)).toBeNull();
  });

  it("reads the whole reply again when its Given label arrives after a card and a bold label", () => {
    // Worked is read over the whole reply: a law-name heading before an answer card turns
    // worked when a Given arrives after the card.
    const text = [
      "**Speed**",
      "$v = d / t$",
      "",
      "```answer",
      "v = 2",
      "```",
      "",
      "A paragraph after the card.",
      "",
      "**Given**",
      "$d = 10$",
      "",
      "Done.",
      "",
    ].join("\n");
    expect(firstDifference(text)).toBeNull();
  });

  it.each([
    ["a blank line", ["**Speed**", "", "$v = d / t$"]],
    ["a maths fence", ["**Speed**", "```math", "v = d / t", "```"]],
  ])("reads the whole reply again when a Given follows a bold label over %s", (_name, label) => {
    const text = [
      ...label,
      "",
      "```answer",
      "v = 2",
      "```",
      "",
      "A paragraph after the card.",
      "",
      "**Given**",
      "$d = 10$",
      "",
      "Done.",
      "",
    ].join("\n");
    expect(firstDifference(text)).toBeNull();
  });

  it("preprocesses part (b) after its card as a worked reply's, cut or whole", () => {
    const reply = physics.replies.projectile_parts.reply;
    const whole = preprocessMarkdown(reply, formatAssistantMathExpr);
    // Every part's formula heading keeps its maths on the next row of one paragraph.
    expect(whole.match(/\*\*Projectile motion formula\*\* {2}\n\$/g)).toHaveLength(3);
    expect(firstDifference(reply)).toBeNull();
    expect(partsOf(reply)).toBeGreaterThanOrEqual(8);
  });

  it("draws a list's members the same streamed a line at a time as settled", () => {
    const reply = SCAN_LAYOUT_LISTS[0]![1];
    expect(firstDifference(reply)).toBeNull();
    const whole = preprocessMarkdown(reply, formatAssistantMathExpr);
    expect(preprocessSettledMarkdown(reply, streamedCache(reply), formatAssistantMathExpr)).toBe(whole);
    // Both members stay under item 1: neither is lifted to the margin.
    expect(whole).toContain("    - **Physics**");
    expect(whole).toContain("    - **Chemistry**");
  });

  it("cuts long replies into many parts", () => {
    expect(partsOf(STREAMING_REPLIES.maths)).toBeGreaterThanOrEqual(10);
    expect(partsOf(physics.replies.projectile_parts.reply)).toBeGreaterThanOrEqual(8);
    expect(partsOf(STREAMING_REPLIES.tips)).toBeGreaterThanOrEqual(3);
  });
});

/** The cache a reply's stream ends with, streamed a line at a time up to `draft`. */
function streamedCache(draft: string): StreamingPreprocessCache | null {
  let cache: StreamingPreprocessCache | null = null;
  for (const end of lineEnds(draft)) {
    cache = preprocessMarkdownForStream(draft.slice(0, end), cache, formatAssistantMathExpr).cache;
  }
  return cache;
}

/** Where settling `saved` after streaming `draft` differs from preprocessing it whole. */
function settleDifference(draft: string, saved: string): string | null {
  const settled = preprocessSettledMarkdown(saved, streamedCache(draft), formatAssistantMathExpr);
  return settled === preprocessMarkdown(saved, formatAssistantMathExpr) ? null : saved;
}

describe("settling a streamed reply", () => {
  const all = [...replies, ...longReplies];

  it("gives every corpus reply what preprocessing it whole gives", () => {
    // Saved as streamed, and as the server keeps it: trimmed, its last line open.
    const differ = all.filter(
      ([, text]) => settleDifference(text, text) !== null || settleDifference(text, text.trim()) !== null,
    );
    expect(differ.map(([name]) => name)).toEqual([]);
  });

  it("gives a saved reply that differs from its stream what preprocessing it whole gives", () => {
    const differ = all.filter(([, text]) => {
      const lines = text.trim().split("\n");
      const cut = Math.floor(lines.length / 2);
      // The stream stopped early, the server added a closing note, or a line changed mid-reply.
      const shorter = lines.slice(0, cut).join("\n");
      const appended = `${text.trim()}\n\n**Given** the note above, that is the answer.`;
      const edited = [...lines.slice(0, cut), "A line the server rewrote.", ...lines.slice(cut + 1)].join("\n");
      return [
        settleDifference(shorter, text.trim()),
        settleDifference(text, appended),
        settleDifference(text, edited),
      ].some((at) => at !== null);
    });
    expect(differ.map(([name]) => name)).toEqual([]);
  });

  it("preprocesses the text after the last cut, not the whole reply", () => {
    const long = longReplies.map(([, text]) => text.trim()).join("\n\n");
    const cache = streamedCache(long);
    const whole = preprocessMarkdown(long, formatAssistantMathExpr);
    const read = jest.spyOn(preprocess, "preprocessMarkdown");
    expect(preprocessSettledMarkdown(long, cache, formatAssistantMathExpr)).toBe(whole);
    const chars = read.mock.calls.reduce((sum, [text]) => sum + text.length, 0);
    read.mockRestore();
    // It preprocessed all of it again.
    expect(chars).toBeLessThan(long.length / 10);
  });
});
