import {
  advanceStreamBlocks,
  emptyStreamBlocksState,
  MIN_SETTLED_CHUNK_CHARS,
} from "@/lib/markdownStreamBlocks";

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

  it("never cuts between list items so ordered numbering survives", () => {
    const items = Array.from(
      { length: 12 },
      (_, i) => `${i + 1}. ${"item text ".repeat(8).trim()}`,
    ).join("\n\n");
    const prepared = `${items}\n\n${PARA("After the list.")}\n\ntail`;
    const state = advanceStreamBlocks(null, prepared, prepared.length);

    for (const chunk of state.chunks) {
      const t = chunk.trimEnd();
      // A chunk may contain the whole list, but must not end mid-list.
      if (/^\d+\.\s/m.test(chunk)) {
        expect(/\n\d+\.\s[^\n]*$/.test(t) && !t.endsWith("After the list.")).toBe(
          false,
        );
      }
    }
    // The list is glued together: no chunk boundary directly precedes an item
    // other than the first.
    const boundaries = state.chunks.map((c) => c.length);
    let offset = 0;
    for (const len of boundaries) {
      offset += len;
      const next = prepared.slice(offset, offset + 12);
      expect(/^\d+\.\s/.test(next)).toBe(false);
    }
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
    expect(emptyStreamBlocksState()).toEqual({ chunks: [], settledText: "" });
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

  it("never cuts inside an open fence/math even with the eager rich-block path", () => {
    const prepared = "```math\nx = 1\n\ny = 2\n```\n\ntail";
    const state = advanceStreamBlocks(null, prepared, prepared.length);

    for (const chunk of state.chunks) {
      const fenceMarkers = chunk.match(/^```/gm)?.length ?? 0;
      expect(fenceMarkers % 2).toBe(0);
    }
  });
});
