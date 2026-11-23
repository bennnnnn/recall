/**
 * A reply streamed flush by flush settles to exactly the text the same reply
 * is preprocessed to whole, as a saved row is: the stream's caches and cuts
 * only save work. (That its pieces draw as the whole does is
 * markdownStreamPieces.test.tsx, which renders both.) Real replies (the
 * streaming fixtures, the physics and chemistry replies, the API's sweep
 * corpus) and the flush benchmark's long ones, in 30- and 7-character flushes.
 */
import { BENCH_REPLIES } from "@/lib/__tests__/fixtures/benchReplies";
import { STREAMING_REPLIES } from "@/lib/__tests__/fixtures/streamingReplies";
import { rowMarkdown, streamReply } from "@/lib/__tests__/support/streamBench";
import { preprocessMarkdown } from "@/lib/markdown/preprocess";
import { formatAssistantMathExpr } from "@/lib/math/formatInput";

import chemistry from "../../../../../docs/fixtures/chemistry_replies.json";
import physics from "../../../../../docs/fixtures/physics_replies.json";
import presentation from "../../../../../docs/fixtures/presentation_cases.json";
import chatCode from "../../../../api/app/tests/behavior/sweep_corpus/chat_code.json";
import followups from "../../../../api/app/tests/behavior/sweep_corpus/followups.json";
import lifeAdmin from "../../../../api/app/tests/behavior/sweep_corpus/life_admin.json";
import mathScience from "../../../../api/app/tests/behavior/sweep_corpus/math_science.json";
import wordProblems from "../../../../api/app/tests/behavior/sweep_corpus/stem_word_problems.json";
import writing from "../../../../api/app/tests/behavior/sweep_corpus/writing.json";

jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("expo-file-system/legacy", () => ({ cacheDirectory: "file:///cache/" }));
jest.mock("@/components/LinkPreviewCard", () => ({ LinkPreviewCard: () => null }));

type Reply = [name: string, text: string];

const sweep: Reply[] = [chatCode, followups, lifeAdmin, mathScience, wordProblems, writing]
  .flat()
  .flatMap((turn: { id: string; reply?: string }): Reply[] =>
    typeof turn.reply === "string" ? [[turn.id, turn.reply]] : [],
  );

/** A step line inside an indented maths fence: the passes close the fence there (review). */
const INTERRUPTED: Reply = ["interrupted-indented-math", ["1. **Set up:**", "   ```math", "   x + 2 = 5", "2. **Simplify:** take 2 away.", "   ```", "", "Then we check the result.", "", "$$", "x = 3", "$$", ""].join("\n")];

/** The same at the margin: the passes close a maths fence at a step line whatever its indent. */
const INTERRUPTED_AT_MARGIN: Reply = ["interrupted-math", ["Set up:", "```math", "x + 2 = 5", "2. **Simplify:** take 2 away.", "```", "", "Then we check the result.", "", "$$", "x = 3", "$$", ""].join("\n")];

const replies: Reply[] = [
  INTERRUPTED,
  INTERRUPTED_AT_MARGIN,
  ...Object.entries(STREAMING_REPLIES),
  ...Object.entries(physics.replies).map(([name, entry]): Reply => [name, entry.reply]),
  ...Object.entries(chemistry.replies).map(([name, entry]): Reply => [name, entry.reply]),
  ...presentation.cases.map((c): Reply => [c.id, c.input]),
  ...sweep,
];

/** The replies whose streamed and whole texts differ, with the first place they do. */
function differences(list: Reply[], step: number): { name: string; at: number }[] {
  return list.flatMap(([name, text]) => {
    // With the maths formatter the reply row passes (ReplyMarkdown).
    const whole = preprocessMarkdown(rowMarkdown(text, false), formatAssistantMathExpr);
    const { settled } = streamReply(text, step, formatAssistantMathExpr);
    if (settled === whole) return [];
    let at = 0;
    while (at < whole.length && settled[at] === whole[at]) at += 1;
    return [{ name, at }];
  });
}

describe("a streamed reply settles to what the whole reply draws", () => {
  it.each([30, 7])("corpus replies in %i-character flushes", (step) => {
    expect(differences(replies, step)).toEqual([]);
  });

  it("the long benchmark replies in 30-character flushes", () => {
    expect(differences(Object.entries(BENCH_REPLIES), 30)).toEqual([]);
  });
});
