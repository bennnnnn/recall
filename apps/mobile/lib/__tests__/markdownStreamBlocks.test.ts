import {
  advanceStreamBlocks,
  settleStreamBlocks,
  emptyStreamBlocksState,
  MIN_SETTLED_CHUNK_CHARS,
} from "@/lib/markdown/streamBlocks";
import {
  BULLET_CODE_STEPS_REPLY,
  CODE_STEPS_REPLY,
  MID_REFERENCES_REPLY,
} from "@/lib/__tests__/fixtures/streamingReplies";
import { pieceRefs } from "@/lib/markdown/streamReferences";

const PARA = (label: string) =>
  `${label} ${"lorem ipsum dolor sit amet ".repeat(16).trim()}`;

describe("advanceStreamBlocks", () => {
  it("settles a paragraph at a blank-line boundary once large enough", () => {
    const prepared = `${PARA("First.")}\n\n${PARA("Second.")}\n\ntail…`;
    const state = advanceStreamBlocks(null, prepared, prepared.length);

    expect(state.chunks.length).toBeGreaterThanOrEqual(1);
    expect(state.chunks.join("")).toBe(state.settledText);
    expect(prepared.startsWith(state.settledText)).toBe(true);
    // Chunks end right before the next block starts (cut after the blank run).
    expect(state.chunks[0].endsWith("\n\n")).toBe(true);
  });

  it("keeps everything in the tail until the minimum chunk size is reached", () => {
    const prepared = "Short.\n\nAlso short.\n\n";
    expect(prepared.length).toBeLessThan(MIN_SETTLED_CHUNK_CHARS);
    const state = advanceStreamBlocks(null, prepared, prepared.length);

    expect(state.chunks).toHaveLength(0);
    expect(state.settledText).toBe("");
  });

  it("is append-only while the same reply grows", () => {
    const first = `${PARA("First.")}\n\n${PARA("Second.")}\n\n`;
    const grown = `${first}${PARA("Third.")}\n\nstill streaming`;

    const s1 = advanceStreamBlocks(null, first, first.length);
    const s2 = advanceStreamBlocks(s1, grown, grown.length);

    expect(s2.chunks.slice(0, s1.chunks.length)).toEqual(s1.chunks);
    expect(s2.settledText.startsWith(s1.settledText)).toBe(true);
  });

  it("returns the same state object when nothing new settles", () => {
    const prepared = `${PARA("First.")}\n\n${PARA("Second.")}\n\n`;
    const s1 = advanceStreamBlocks(null, prepared, prepared.length);
    const s2 = advanceStreamBlocks(s1, `${prepared}tail`, prepared.length);

    expect(s2).toBe(s1);
  });

  it("never cuts inside a fenced code block (even across blank lines)", () => {
    const fenceBody = `line one\n\n${PARA("looks like prose")}\n\nline two`;
    const prepared = `\`\`\`python\n${fenceBody}\n\`\`\`\n\n${PARA("After.")}\n\ntail`;
    const state = advanceStreamBlocks(null, prepared, prepared.length);

    for (const chunk of state.chunks) {
      const fenceMarkers = chunk.match(/^```/gm)?.length ?? 0;
      expect(fenceMarkers % 2).toBe(0);
    }
  });

  it("cuts a numbered list from item 2: every column up to 99 is two digits wide", () => {
    const items = Array.from(
      { length: 12 },
      (_, i) => `${i + 1}. ${"item text ".repeat(40).trim()}`,
    ).join("\n\n");
    const prepared = `${items}\n\n${PARA("After the list.")}\n\ntail`;
    const state = advanceStreamBlocks(null, prepared, prepared.length);

    expect(state.chunks.length).toBeGreaterThan(1);
    expect(state.chunks[1]!.startsWith("2. ")).toBe(true);
    // The chunk ends inside the list: it is drawn as a list that goes on.
    expect(state.continued[0]).toBe(true);
    expect(state.listAfter[0]).toEqual(
      expect.objectContaining({ marker: ".", next: 2, irregular: false, wide: false }),
    );
  });

  it("respects the safeLen bound", () => {
    const prepared = `${PARA("First.")}\n\n${PARA("Second.")}\n\ntail`;
    const state = advanceStreamBlocks(null, prepared, 10);

    expect(state.chunks).toHaveLength(0);
  });

  it("resets when the content no longer extends the settled prefix", () => {
    const streamed = `${PARA("First.")}\n\n${PARA("Second.")}\n\n`;
    const s1 = advanceStreamBlocks(null, streamed, streamed.length);
    expect(s1.chunks.length).toBeGreaterThan(0);

    const finalContent = `${PARA("Rewritten.")}\n\n${PARA("Body.")}\n\nend`;
    const s2 = advanceStreamBlocks(s1, finalContent, finalContent.length);

    expect(finalContent.startsWith(s2.settledText)).toBe(true);
    expect(s2.chunks.join("")).toBe(s2.settledText);
  });

  it("starts from a clean state helper", () => {
    expect(emptyStreamBlocksState()).toEqual({
      chunks: [],
      continued: [],
      listAfter: [],
      settledText: "",
      refs: [],
    });
  });

  it(
    "BUG FIX regression: cuts a chunk right after a short closed ```math " +
      "fence instead of waiting for MIN_SETTLED_CHUNK_CHARS",
    () => {
      // Mirrors a real step-by-step math reply: each step's fence body is
      // tiny (well under 320 chars), so under the old size-only threshold
      // this whole segment stayed in the re-parsed-every-flush pending
      // region — remounting the fence's KaTeX WebView on every flush — for
      // as long as it took later steps to push the total past 320 chars.
      const step =
        "1. Subtract 2 from both sides:\n\n```math\nx^2 + 2 - 2 = 6 - 2\n```\n\nSimplify: x^2 = 4\n\n";
      expect(step.length).toBeLessThan(MIN_SETTLED_CHUNK_CHARS);
      const prepared = `${step}2. Take the square root:`;
      const state = advanceStreamBlocks(null, prepared, prepared.length);

      expect(state.chunks.length).toBeGreaterThanOrEqual(1);
      expect(state.chunks[0]).toContain("```math");
      expect(state.settledText.length).toBeLessThan(prepared.length);
    },
  );

  it("still requires a closed fence, not just any short blank-separated text, to cut early", () => {
    // Plain prose with no rich block keeps the existing size-based batching
    // — only a fence/math block should bypass MIN_SETTLED_CHUNK_CHARS.
    const prepared = "Short.\n\nAlso short.\n\ntail";
    expect(prepared.length).toBeLessThan(MIN_SETTLED_CHUNK_CHARS);
    const state = advanceStreamBlocks(null, prepared, prepared.length);

    expect(state.chunks).toHaveLength(0);
  });

  it("cuts eagerly after a short closed $$ display-math block too", () => {
    const prepared = "Here:\n\n$$x^2 = 4$$\n\nDone.\n\ntail";
    expect(prepared.length).toBeLessThan(MIN_SETTLED_CHUNK_CHARS);
    const state = advanceStreamBlocks(null, prepared, prepared.length);

    expect(state.chunks.length).toBeGreaterThanOrEqual(1);
    expect(state.chunks[0]).toContain("$$x^2 = 4$$");
  });

  // Review #2606: counted raw, "$$–$$$" and "$$." left a formula open, and no part after them
  // was ever cut.
  it("cuts after a list priced in $$ tiers: a tier opens no formula", () => {
    const prepared = `1. Nopa – $$–$$$\n2. Zuni – $$.\n\n${PARA("Both take bookings.")}\n\n${PARA("More.")}\n\ntail`;
    const state = advanceStreamBlocks(null, prepared, prepared.length);
    expect(state.chunks.length).toBeGreaterThanOrEqual(1);
    expect(state.chunks.join("")).toContain("Both take bookings.");
  });

  it("never cuts inside an open fence/math even with the eager rich-block path", () => {
    const prepared = "```math\nx = 1\n\ny = 2\n```\n\ntail";
    const state = advanceStreamBlocks(null, prepared, prepared.length);

    for (const chunk of state.chunks) {
      const fenceMarkers = chunk.match(/^```/gm)?.length ?? 0;
      expect(fenceMarkers % 2).toBe(0);
    }
  });

  it("cuts after a blank before plain text, or before the next item of the open list", () => {
    const parts = [
      `${PARA("One.")}\n\n`,
      // A list's next item may start a chunk; its continuation paragraph may not.
      "- a\n\n  more\n\n",
      "- b\n\n",
      `${PARA("Two.")}\n\n`,
      // A one-line $$…$$ is a rich block: the next safe boundary cuts.
      "Inline $$a$$ here.\n\n",
      // After a quote or a table, plain text past a blank line starts a new block.
      "Short.\n\n",
      "> q\n\n",
      `${PARA("Three.")}\n\n`,
      "| a |\n\n",
      `${PARA("Four.")}\n\nend`,
    ];
    const prepared = parts.join("");
    const state = advanceStreamBlocks(null, prepared, prepared.length);

    expect(state.chunks).toEqual([
      parts.slice(0, 2).join(""),
      parts.slice(2, 5).join(""),
      parts.slice(5, 9).join(""),
    ]);
    expect(state.continued).toEqual([true, false, false]);
  });

  it("settles nothing for a negative safe length", () => {
    const prepared = `${PARA("First.")}\n\n${PARA("Second.")}\n\n`;
    const prev = emptyStreamBlocksState();
    expect(advanceStreamBlocks(prev, prepared, -5)).toBe(prev);
  });
});

describe("advanceStreamBlocks between list items", () => {
  const bullets = (count: number, marker = "-") =>
    Array.from({ length: count }, (_, i) => `${marker} Item ${i + 1}: ${"words ".repeat(14).trim()}`);

  it("cuts a long bullet list between items and says the list goes on", () => {
    const prepared = `Intro.\n\n${bullets(12).join("\n")}\n\nDone.\n\ntail`;
    const state = advanceStreamBlocks(null, prepared, prepared.length);

    expect(state.chunks.length).toBeGreaterThan(1);
    let offset = 0;
    state.chunks.forEach((chunk, index) => {
      offset += chunk.length;
      if (state.continued[index]) {
        expect(prepared.slice(offset)).toMatch(/^- Item \d+:/);
        expect(state.listAfter[index]).toEqual(
          expect.objectContaining({ marker: "-", next: null, irregular: false }),
        );
      }
    });
    expect(state.continued.some(Boolean)).toBe(true);
  });

  it("does not continue a list across a change of bullet marker", () => {
    const prepared = `${bullets(6, "-").join("\n")}\n${bullets(6, "*").join("\n")}\n\ntail`;
    const state = advanceStreamBlocks(null, prepared, prepared.length);
    let offset = 0;
    for (const chunk of state.chunks) {
      offset += chunk.length;
      // The first `*` item opens a new list: never a cut that continues the `-` list.
      expect(prepared.slice(offset).startsWith("* Item 1:")).toBe(false);
    }
  });

  it("never cuts a numbered list whose numbers do not run on", () => {
    const repeated = Array.from({ length: 14 }, () => `1. ${"step words ".repeat(10).trim()}`);
    const prepared = `${repeated.join("\n")}\n\ntail`;
    expect(advanceStreamBlocks(null, prepared, prepared.length).chunks).toEqual([]);
  });

  it("cuts a short numbered list too (#2601's numbered main items)", () => {
    const short = Array.from({ length: 9 }, (_, i) => `${i + 1}. ${"step words ".repeat(10).trim()}`);
    const prepared = `${short.join("\n")}\n\ntail`;
    const state = advanceStreamBlocks(null, prepared, prepared.length);
    expect(state.chunks.length).toBeGreaterThan(0);
    expect(state.continued.every(Boolean)).toBe(true);
  });

  it("does not cut a list after a line markdown may read as part of an item", () => {
    const lines = bullets(4);
    const prepared = `${lines[0]}\nlazy line of the first item\n${lines.slice(1).join("\n")}\n${bullets(6).join("\n")}\n\ntail`;
    const state = advanceStreamBlocks(null, prepared, prepared.length);
    expect(state.continued.some(Boolean)).toBe(false);
  });

  it("carries the open list across flushes", () => {
    const lines = Array.from({ length: 14 }, (_, i) => `${i + 1}. ${"step words ".repeat(10).trim()}`);
    const full = `${lines.join("\n")}\n\ntail`;
    const upTo = (n: number) => `${lines.slice(0, n).join("\n")}\n`;
    let state = advanceStreamBlocks(null, upTo(2), upTo(2).length);
    expect(state.chunks).toEqual([]);
    state = advanceStreamBlocks(state, upTo(5), upTo(5).length);
    expect(state.continued).toEqual([true]);
    expect(upTo(5).slice(state.settledText.length).startsWith("4. ")).toBe(true);
    const final = advanceStreamBlocks(state, full, full.length);
    expect(final.chunks.slice(0, 1)).toEqual(state.chunks);
  });

  it("drops a chunk drawn as a list that goes on once the text after it no longer does", () => {
    const lines = Array.from({ length: 4 }, (_, i) => `${i + 1}. ${"step words ".repeat(10).trim()}`);
    const streamed = `${lines.join("\n")}\n`;
    const state = advanceStreamBlocks(null, streamed, streamed.length);
    expect(state.continued).toEqual([true]);
    const chunk = state.chunks[0]!;

    // The same text after it: kept.
    expect(advanceStreamBlocks(state, `${streamed}\nDone.`, 0).chunks).toEqual([chunk]);
    // Its list ends where the chunk does: the chunk is drawn again with its end.
    for (const after of ["Done.\n", "- a bullet\n", "12. skipped a number\n"]) {
      expect(advanceStreamBlocks(state, `${chunk}${after}`, 0).chunks).toEqual([]);
    }
  });

  it("draws a reply holding a link reference definition in one piece, from the line it arrives", () => {
    const body = `${PARA("Cites [a source][1] here.")}\n\n${PARA("Second.")}\n\n${PARA("Third.")}\n\n`;
    const before = advanceStreamBlocks(null, body, body.length);
    expect(before.chunks.length).toBeGreaterThan(0);

    const withDefinition = `${body}[1]: https://example.com/article\n`;
    const after = advanceStreamBlocks(before, withDefinition, withDefinition.length);
    expect(after.chunks).toEqual([]);
    // Later flushes keep the reference and its use in one piece; the text after them may be cut.
    const later = `${withDefinition}\n${PARA("More text after it.")}\n\n${PARA("And more.")}\n\nend`;
    const grown = advanceStreamBlocks(after, later, later.length);
    const holder = grown.chunks.find((chunk) => chunk.includes("[a source][1]"));
    expect(holder).toContain("[1]: https://example.com/article");
    expect(grown.chunks.join("")).toBe(grown.settledText);
    // A reply whose definition is still in its last, open line settles in one piece too.
    expect(settleStreamBlocks(before, `${body}[1]: https://example.com/article`).chunks).toEqual([]);
  });

  it("cuts a long how-to between its steps, each with an indented fence (audit MX-2)", () => {
    const state = advanceStreamBlocks(null, CODE_STEPS_REPLY, CODE_STEPS_REPLY.length);
    expect(state.continued.filter(Boolean).length).toBeGreaterThan(1);
    expect(state.chunks.join("")).toBe(state.settledText);
    // A fence line left of the item's content ends the item: no cut in that list after it.
    // A closer left of the item's content ends the item and its fence, and opens a fence of
    // its own (markdown-it), which runs to the next bare one: no cut lands inside it.
    const opener = CODE_STEPS_REPLY.replace("   ```\n\n   It prints `done 3`", "```\n\n   It prints `done 3`");
    const opensAt = opener.indexOf("```\n\n   It prints `done 3`");
    const closesAt = opener.indexOf("   ```\n", opener.indexOf("npm run step-4"));
    let offset = 0;
    for (const chunk of advanceStreamBlocks(null, opener, opener.length).chunks) {
      offset += chunk.length;
      expect(offset > opensAt && offset <= closesAt).toBe(false);
    }
    expect(state.chunks.some((chunk) => /^\d+\. /.test(chunk))).toBe(true);
    // A bullet list goes on across an item's fence: the next bullet is a cut, drawn as a list that goes on.
    const para = "lorem ipsum dolor sit amet ".repeat(14);
    const bullets = [`- a ${para}`, "  ```", "  x", "  ```", `- b ${para}`, `- c ${para}`, "", "Done."].join("\n");
    const bulletCut = advanceStreamBlocks(null, bullets, bullets.length);
    expect(bulletCut.chunks[0]?.endsWith("  ```\n")).toBe(true);
    expect(bulletCut.continued[0]).toBe(true);
    // An item's fence left open by a bullet at the margin still keeps that list a task list.
    const unclosed = ["- [ ] Install:", "  ```bash", "  npm i", `- Build ${para}`, `- Test ${para}`, `- [x] Lint ${para}`, "", "Done."].join("\n");
    expect(advanceStreamBlocks(null, unclosed, unclosed.length).continued.some(Boolean)).toBe(false);
    // "Then run:" ends the list (nothing goes on lazily after a fence): its fence is the
    // top level's, whatever its indent, and no cut lands inside it (audit review).
    const ended = ["- Install it:", "  ```bash", "  npm i", "  ```", "Then run:", "  ```bash", "npm run build", "",
      `npm test ${para}`, `npm run lint ${para}`, "  ```", "Done.", "", para].join("\n");
    const topOpens = ended.indexOf("  ```bash", ended.indexOf("Then run:"));
    const topCloses = ended.lastIndexOf("  ```");
    let end = 0;
    for (const chunk of advanceStreamBlocks(null, ended, ended.length).chunks) {
      end += chunk.length;
      expect(end > topOpens && end <= topCloses).toBe(false);
    }
    // A closer at the margin ends the item and opens a top-level fence: prose after it is code
    // until the next bare ```, and no cut lands inside.
    const margin = ["- a", "  ```", "  x", "```", "", `First ${para}`, "", `Second ${para}`, "", "```", "", "After."].join("\n");
    const marginOpens = margin.indexOf("```\n\nFirst");
    const marginCloses = margin.lastIndexOf("```");
    let marginEnd = 0;
    for (const chunk of advanceStreamBlocks(null, margin, margin.length).chunks) {
      marginEnd += chunk.length;
      expect(marginEnd > marginOpens && marginEnd <= marginCloses).toBe(false);
    }
    // A lazy line bends a task list; its items after a fence are still that list, never cut.
    const lazyTasks = ["- [x] Install it:", "Then run:", "  ```", "  npm i", "  ```", `- Build ${para}`, `- Test ${para}`, `- [ ] Lint ${para}`, "", "Done."].join("\n");
    expect(advanceStreamBlocks(null, lazyTasks, lazyTasks.length).continued.some(Boolean)).toBe(false);
    // The same with the fence's body at the margin: that line ends the item, and the next
    // indented ``` opens a top-level fence that runs to the end: nothing after it is cut.
    const outdented = ["- [x] Install it:", "Then run:", "  ```", "npm i", "  ```", "- Build", "", `First ${para}`, "", `Second ${para}`].join("\n");
    const runsFrom = outdented.indexOf("  ```\n- Build");
    let outEnd = 0;
    for (const chunk of advanceStreamBlocks(null, outdented, outdented.length).chunks) {
      outEnd += chunk.length;
      expect(outEnd > runsFrom).toBe(false);
    }
    // Under a line of text "2." is that text, not a list (markdown starts one there only at 1):
    // its fence is the top level's and no cut lands inside it.
    const notList = ["Continuing from step 1:", "2. Add the services:", "   ```yaml", "services:", `- web ${para}`, `- db ${para}`, "   ```", "", "Done."].join("\n");
    const yamlOpens = notList.indexOf("   ```yaml");
    const yamlCloses = notList.lastIndexOf("   ```");
    let yamlEnd = 0;
    for (const chunk of advanceStreamBlocks(null, notList, notList.length).chunks) {
      yamlEnd += chunk.length;
      expect(yamlEnd > yamlOpens && yamlEnd <= yamlCloses).toBe(false);
    }
    // A heading under an item ends the list (only a paragraph goes on lazily): its fence is the
    // top level's, and the line at the margin inside it does not close it.
    const headed = ["- Install:", "# Setup", "  ```bash", "  npm i", "cp .env x", "", `echo done ${para}`, "", `echo again ${para}`, "  ```", "", "Then start."].join("\n");
    const headedOpens = headed.indexOf("  ```bash");
    const headedCloses = headed.lastIndexOf("  ```");
    let headedEnd = 0;
    for (const chunk of advanceStreamBlocks(null, headed, headed.length).chunks) {
      headedEnd += chunk.length;
      expect(headedEnd > headedOpens && headedEnd <= headedCloses).toBe(false);
    }
    // Under a heading in an item nothing goes on lazily: "Use Homebrew:" ends the list, and the
    // fence after it is the top level's. So is a fence after one opened outside the item.
    const underHeading = ["1. **Install**", "   ### On macOS", "Use Homebrew:", "   ```bash", "brew install node", "",
      `brew install pnpm ${para}`, "", `brew doctor ${para}`, "   ```", "More text"].join("\n");
    const afterTopFence = ["- [ ] a", "lazy", "```", "top", "```", "  ```", "x", "", `y ${para}`, "", `z ${para}`, "  ```", "End."].join("\n");
    for (const [text, opener] of [[underHeading, "   ```bash"], [afterTopFence, "  ```\nx"]] as const) {
      const opens = text.indexOf(opener);
      const closes = text.lastIndexOf("```");
      let end = 0;
      for (const chunk of advanceStreamBlocks(null, text, text.length).chunks) {
        end += chunk.length;
        expect(end > opens && end <= closes).toBe(false);
      }
    }
    // After a rule in an item nothing goes on lazily either: "Then run:" ends the list.
    const ruled = ["- Install the tools", "", "  ---", "Then run:", "  ```bash", "npm i", "", `npm run build ${para}`, "",
      `npm test ${para}`, "  ```", "", "Done."].join("\n");
    const ruledOpens = ruled.indexOf("  ```bash");
    const ruledCloses = ruled.lastIndexOf("  ```");
    let ruledEnd = 0;
    for (const chunk of advanceStreamBlocks(null, ruled, ruled.length).chunks) {
      ruledEnd += chunk.length;
      expect(ruledEnd > ruledOpens && ruledEnd <= ruledCloses).toBe(false);
    }
    // The same after an item's fence indented 4 spaces, which only the loose reader sees.
    const fourSpace = ["- Install the tools:", "    ```bash", "    npm i", "    ```", "Then run:", "  ```bash", "npm run build", "",
      `npm test ${para}`, "", `npm run lint ${para}`, "  ```", "", "Done."].join("\n");
    const fourOpens = fourSpace.indexOf("  ```bash\nnpm run build");
    const fourCloses = fourSpace.lastIndexOf("  ```");
    let fourEnd = 0;
    for (const chunk of advanceStreamBlocks(null, fourSpace, fourSpace.length).chunks) {
      fourEnd += chunk.length;
      expect(fourEnd > fourOpens && fourEnd <= fourCloses).toBe(false);
    }
    // In a task list a done item drawn apart from a later open one would draw as a check: no cut.
    const tasks = ["- [x] Install:", "", "  ```bash", "  npm i", "  ```", "", "- [ ] Configure", "", "Done."].join("\n");
    expect(advanceStreamBlocks(null, tasks, tasks.length).continued.some(Boolean)).toBe(false);
    // Nor after a fence, nor once the list is long enough to cut.
    const note = "lorem ipsum dolor sit amet ".repeat(4);
    const fenced = ["- [ ] Install:", "", "  ```bash", "  npm i", "  ```", "", `- Build ${note}`, `- Test ${note}`, `- [x] Lint ${note}`, "", "Done."].join("\n");
    const long = Array.from({ length: 12 }, (_, i) => `- [${i < 10 ? "x" : " "}] Task ${i} ${note}`).join("\n");
    for (const text of [fenced, `${long}\n\nDone.`]) {
      expect(advanceStreamBlocks(null, text, text.length).continued.some(Boolean)).toBe(false);
    }
  });

  it("ties only the pieces from a reference's first use to its definition (audit MX-3)", () => {
    const head = `${PARA("Opening, no links.")}\n\n${PARA("Still none.")}\n\n`;
    const cited = `${PARA("Cites [a source][1] here.")}\n\n[1]: https://example.com/article\n\n`;
    const rest = Array.from({ length: 6 }, (_, i) => PARA(`After ${i}.`)).join("\n\n");
    const text = `${head}${cited}${rest}\n\nend`;
    let state = advanceStreamBlocks(null, "", 0);
    for (let end = 30; end < text.length; end += 30) {
      state = advanceStreamBlocks(state, text.slice(0, end), end);
    }
    state = advanceStreamBlocks(state, text, text.length);
    // The chunks before the use stay; the use and its definition are one chunk; the text after is cut.
    expect(state.chunks.slice(0, 2)).toEqual([`${PARA("Opening, no links.")}\n\n`, `${PARA("Still none.")}\n\n`]);
    expect(state.chunks.find((c) => c.includes("[a source][1]"))).toContain("[1]: https://example.com/article");
    expect(state.chunks.length).toBeGreaterThan(4);
    expect(state.chunks.join("")).toBe(state.settledText);
    // Settled, the pieces are the same.
    expect(settleStreamBlocks(state, text).chunks).toEqual(state.chunks);
  });

  it("cuts the fixtures markdownStreamPieces draws: bullet steps with fences, a reference mid-reply", () => {
    const steps = advanceStreamBlocks(null, BULLET_CODE_STEPS_REPLY, BULLET_CODE_STEPS_REPLY.length);
    expect(steps.continued.filter(Boolean).length).toBeGreaterThan(2);
    const refs = advanceStreamBlocks(null, MID_REFERENCES_REPLY, MID_REFERENCES_REPLY.length);
    const tied = refs.chunks.findIndex((chunk) => chunk.includes("[guide][1]"));
    expect(tied).toBeGreaterThan(0);
    expect(refs.chunks[tied]).toContain("[the docs]: https://docs.example.com");
    expect(refs.chunks.length).toBeGreaterThan(tied + 1);
  });

  it("reads a definition whose title runs over several lines", () => {
    const text = 'Intro.\n\n[docs]: https://docs.example.com "one\ntwo\nthree\nfour"\n\nAfter.';
    expect(pieceRefs(text).defines).toEqual(["DOCS"]);
  });

  it.each([
    ["a label broken over a quote's lines", "> As the [style\n> guide] says.", "[style guide]: https://x.com"],
    ["an escaped bracket in the label", "See [a\\]b] here.", "[a\\]b]: https://x.com"],
  ])("ties a use to its definition: %s", (_name, use, definition) => {
    const filler = Array.from({ length: 4 }, (_, i) => PARA(`Filler ${i}.`)).join("\n\n");
    const text = `${use}\n\n${filler}\n\n${definition}\n\n${PARA("After.")}\n\n${PARA("End.")}\n\nend`;
    const state = advanceStreamBlocks(null, text, text.length);
    const holder = state.chunks.find((chunk) => chunk.includes(use));
    expect(holder ?? "").toContain(definition);
  });

  it.each([
    ["a quote", "> [1]: https://x.com"],
    ["a list item", "- [1]: https://x.com"],
  ])("ties a use to a definition in %s", (_name, definition) => {
    const filler = Array.from({ length: 4 }, (_, i) => PARA(`Filler ${i}.`)).join("\n\n");
    const text = `${PARA("See [1].")}\n\n${filler}\n\n${definition}\n\n${PARA("After.")}\n\n${PARA("End.")}\n\nend`;
    const state = advanceStreamBlocks(null, text, text.length);
    const holder = state.chunks.find((chunk) => chunk.includes("See [1]."));
    expect(holder).toContain(definition);
  });

  it("cuts on after a line that only looks like a definition", () => {
    const paras = Array.from({ length: 6 }, (_, i) => PARA(`Para ${i}.`)).join("\n\n");
    const text = `[Note]: see the list below\n\n${paras}\n\n${PARA("As in [Note].")}\n\n${PARA("Last.")}\n\nend`;
    expect(pieceRefs("[Note]: see the list below\n").defines).toEqual([]);
    const state = advanceStreamBlocks(null, text, text.length);
    // The line defines nothing, so the later "[Note]" ties nothing: the pieces between stay cut.
    expect(state.chunks.length).toBeGreaterThan(5);
    expect(state.chunks[0]).not.toContain("As in [Note].");
  });

  it("reads an empty numbered item under a line of text as that text, not a list to cut", () => {
    const items = Array.from({ length: 12 }, (_, i) => `${i + 2}. ${"word ".repeat(12)}`).join("\n");
    const text = `Steps:\n1. \n${items}\n\nDone.`;
    expect(advanceStreamBlocks(null, text, text.length).continued.some(Boolean)).toBe(false);
  });

  it("ties a use that arrives after its definition was cut into a chunk", () => {
    const first = `${PARA("Defines it.")}\n\n[docs]: https://docs.example.com\n\n${PARA("Gap one.")}\n\n${PARA("Gap two.")}\n\n`;
    const cut = advanceStreamBlocks(null, first, first.length);
    expect(cut.chunks.length).toBeGreaterThanOrEqual(2);
    const used = `${first}${PARA("Now see [docs].")}\n\n${PARA("Tail.")}\n\n`;
    const tied = advanceStreamBlocks(cut, used, used.length);
    const holder = tied.chunks.find((c) => c.includes("[docs]: https"));
    expect(holder).toContain("Now see [docs].");
    expect(tied.chunks.join("")).toBe(tied.settledText);
  });

  it("cuts a numbered list that reaches 100 nowhere, even after it was cut while shorter", () => {
    const items = (from: number, to: number) =>
      Array.from({ length: to - from + 1 }, (_, i) => `${from + i}. word number ${from + i} with a short gloss`).join("\n");
    const short = `Words:\n\n${items(1, 60)}\n`;
    const cut = advanceStreamBlocks(null, short, short.length);
    expect(cut.continued.some(Boolean)).toBe(true);

    const long = `Words:\n\n${items(1, 102)}\n`;
    const grown = advanceStreamBlocks(cut, long, long.length);
    expect(grown.continued.some(Boolean)).toBe(false);
    expect(grown.settledText.length).toBeLessThan(long.indexOf("1. word"));
    // And it stays uncut as it goes on.
    const longer = `${long}${items(103, 110)}\n`;
    expect(advanceStreamBlocks(grown, longer, longer.length).continued.some(Boolean)).toBe(false);

    // A reply that only reaches 100 in its last line settles with the list whole.
    const settled = settleStreamBlocks(cut, `Words:\n\n${items(1, 100)}`);
    expect(settled.continued.some(Boolean)).toBe(false);
  });

  it("does not cut a numbered list after a line indented left of its item's content", () => {
    const phases = Array.from({ length: 16 }, (_, i) =>
      [`${i + 1}. Phase ${i + 1} ${"words ".repeat(8).trim()}`, `   - detail of phase ${i + 1}`].join("\n"),
    );
    const prepared = `Plan:\n\n${phases.join("\n")}\n\nDone.\n\ntail`;
    // `10. ` puts item 10's content at column 4: its `   - detail` (column 3) is not inside it.
    // The list runs on to item 10, so a cut before it stands; none lands after it.
    const state = advanceStreamBlocks(null, prepared, prepared.length);
    const tenAt = prepared.indexOf("10. Phase");
    let offset = 0;
    state.chunks.forEach((chunk, index) => {
      offset += chunk.length;
      if (state.continued[index]) expect(offset).toBeLessThanOrEqual(tenAt);
    });

    // Indented to the item's content, the detail is inside it and the list may be cut.
    const aligned = prepared.replace(/\n   - detail of phase (\d\d)/g, "\n    - detail of phase $1");
    expect(advanceStreamBlocks(null, aligned, aligned.length).continued.some(Boolean)).toBe(true);
  });

  it("drops only the chunks a rewrite changed", () => {
    const streamed = `${PARA("First.")}\n\n${PARA("Second.")}\n\n${PARA("Third.")}\n\n`;
    const s1 = advanceStreamBlocks(null, streamed, streamed.length);
    expect(s1.chunks.length).toBeGreaterThan(1);

    const rewritten = `${s1.chunks[0]}${PARA("Changed.")}\n\n${PARA("More.")}\n\nend`;
    const s2 = advanceStreamBlocks(s1, rewritten, rewritten.length);

    expect(s2.chunks[0]).toBe(s1.chunks[0]);
    expect(s2.chunks.join("")).toBe(s2.settledText);
    expect(rewritten.startsWith(s2.settledText)).toBe(true);
  });
});
