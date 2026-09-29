import { markdownToCopyText, markdownToSpeechText } from "@/lib/markdown/plain";

declare const __dirname: string;

type RenderCase = {
  id: string;
  markdown: string;
  speech?: string;
  speech_contains?: string[];
  copy_contains?: string;
  copy_excludes?: string[];
};

const { readFileSync } = require("fs") as {
  readFileSync: (file: string, encoding: string) => string;
};
const { join } = require("path") as {
  join: (...parts: string[]) => string;
};

const corpus = JSON.parse(
  readFileSync(join(__dirname, "../../../api/app/tests/fixtures/stem_gate_corpus.json"), "utf8"),
) as { render: RenderCase[] };

describe("stem gate render", () => {
  it.each(corpus.render)("$id speaks and copies the shared corpus", (row) => {
    const spoken = markdownToSpeechText(row.markdown);
    const copy = markdownToCopyText(row.markdown);
    if (row.speech) expect(spoken).toBe(row.speech);
    for (const piece of row.speech_contains ?? []) expect(spoken).toContain(piece);
    expect(spoken).not.toMatch(/\\[a-zA-Z]+/);
    if (row.copy_contains) expect(copy).toContain(row.copy_contains);
    for (const piece of row.copy_excludes ?? []) expect(copy).not.toContain(piece);
  });
});
