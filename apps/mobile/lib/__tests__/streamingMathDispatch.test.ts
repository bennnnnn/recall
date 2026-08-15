import { classifyOpenFencePreview } from "@/lib/copyBlock";
import { preprocessMarkdownForStream } from "@/lib/markdownPreprocessStream";
import { classifyOpenStreamTail } from "@/lib/streamingOpenFence";

/**
 * Replay a reply one character at a time through the same branch
 * MarkdownContent uses for the live tail (preprocess → classifyOpenStreamTail
 * → classifyOpenFencePreview). Asserts the *sequence* of preview kinds, which
 * settled-output tests cannot see.
 */
function previewSequence(full: string): string[] {
  const kinds: string[] = [];
  let last = "";
  let cache = null as ReturnType<typeof preprocessMarkdownForStream>["cache"] | null;
  for (let i = 1; i <= full.length; i += 1) {
    const raw = full.slice(0, i);
    const result = preprocessMarkdownForStream(raw, cache);
    cache = result.cache;
    const liveRaw = result.prepared.slice(result.cache.preparedStable.length);
    const open = classifyOpenStreamTail(liveRaw, result.cache.scanState);
    let kind = "other";
    if (open.kind === "fence") {
      kind = classifyOpenFencePreview(open.lang, open.body);
    } else if (open.kind === "math") {
      kind = "math";
    }
    if (kind !== last) {
      kinds.push(kind);
      last = kind;
    }
  }
  return kinds;
}

describe("streaming open-fence math dispatch", () => {
  it("BUG FIX regression: open ```latex never lands on CodeBlock (R1)", () => {
    const seq = previewSequence("Here:\n\n```latex\n\\frac{x^2}{2} = 8\n```\n\nDone.");
    expect(seq).not.toContain("code");
    expect(seq).toContain("math");
  });

  it("BUG FIX regression: open ```math does not flip through AnswerBlock (R2)", () => {
    const seq = previewSequence("```math\n\\frac{x^2}{2} = 8\n```\n");
    expect(seq).not.toContain("answer");
    expect(seq).toContain("math");
  });

  it("BUG FIX regression: open ```graph is a quiet diagram, not raw JSON (R3)", () => {
    const seq = previewSequence('```graph\n{"type":"function","points":[[0,0],[1,1]]}\n```\n');
    expect(seq).not.toContain("code");
    expect(seq).toContain("diagram");
  });
});
