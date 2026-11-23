/**
 * ~20k-character replies for the streaming flush benchmark and the
 * "streams the same as it settles" test. Each holds one shape the audit
 * (docs/COMPLEXITY_TICKETS.md, P1) says slows a stream: a price dollar early on, a
 * worked maths reply, numbered steps with indented code, a link reference
 * definition, and long lists. `corpus` is real replies one after another.
 */
import { STREAMING_REPLIES } from "@/lib/__tests__/fixtures/streamingReplies";

import physics from "../../../../../docs/fixtures/physics_replies.json";
import chatCode from "../../../../api/app/tests/behavior/sweep_corpus/chat_code.json";
import lifeAdmin from "../../../../api/app/tests/behavior/sweep_corpus/life_admin.json";
import mathScience from "../../../../api/app/tests/behavior/sweep_corpus/math_science.json";
import writing from "../../../../api/app/tests/behavior/sweep_corpus/writing.json";

const TARGET = 20_000;
const FENCE = "```";

/** Join `parts` (cycled) with blank lines until the text reaches TARGET characters. */
function fill(head: string, parts: readonly string[]): string {
  let out = head;
  for (let i = 0; out.length < TARGET; i += 1) out += `${parts[i % parts.length]}\n\n`;
  return out;
}

function sweepReplies(...corpora: { reply?: string }[][]): string[] {
  return corpora.flat().flatMap((turn) => (typeof turn.reply === "string" ? [turn.reply] : []));
}

const PROSE = [
  "Most landlords hold the deposit in a protected scheme and return it within ten days of the tenancy ending, less any agreed deductions for damage beyond normal wear.",
  "Before you sign, read the inventory carefully. Photograph every room, note any marks on the walls or carpets, and email the photos to the agent so there is a dated record.",
  "- Check the meter readings on the day you move in.\n- Ask which utilities are included in the rent.\n- Find out who handles repairs, and how to reach them out of hours.",
  "1. Give written notice at the time the contract asks for.\n2. Clean the flat to the standard you found it.\n3. Return every key, including spares.",
  "If a deduction seems unfair, the scheme runs a free dispute service. Send them the inventory, your photos and the emails, and they decide from the evidence alone.",
];

const STEP = (n: number) =>
  `${n}. Install the package and check the version it reports:\n\n   ${FENCE}bash\n   npm install left-pad@${n}.0.0\n   npx left-pad --version\n   ${FENCE}\n\n   The command prints the version it installed. If it prints an older one, clear the cache and run it again.`;

export const BENCH_REPLIES = {
  /** MX-1: one price dollar in the first line holds every later paragraph unstable. */
  price: fill("You will need a $300 deposit to hold the flat, paid by bank transfer.\n\n", PROSE),
  /** MX-2: worked maths replies (bold Given / Required) one after another. */
  worked: fill(
    "",
    Object.values(physics.replies).map((entry) => entry.reply),
  ),
  /** MX-2: a fence indented under a numbered step (not at column 0). */
  steps: fill(
    "Here is how to set it up.\n\n",
    Array.from({ length: 12 }, (_, i) => STEP(i + 1)),
  ),
  /** MX-3: a link reference definition near the top. */
  references: fill("See the guide [1] before you start.\n\n[1]: https://example.com/guide\n\n", PROSE),
  /** Real replies: maths, code, everyday and writing turns. */
  corpus: fill(
    "",
    [
      ...Object.values(STREAMING_REPLIES),
      ...sweepReplies(mathScience, chatCode, lifeAdmin, writing),
    ],
  ),
} as const;
