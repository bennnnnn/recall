import * as markdownPlain from "@/lib/markdownPlain";
import {
  markdownToCopyText,
  markdownToPlainText,
  markdownToSpeechText,
} from "@/lib/markdownPlain";
import { markdownToStructuredPrintHtml } from "@/lib/printDocument";
import { projectLearningToPrintHtml } from "@/lib/exportProjectPdf";
import type { ProjectDetail, ProjectItem } from "@/lib/api";

describe("markdownPlain", () => {
  it("strips fences and markdown emphasis for TTS", () => {
    const plain = markdownToPlainText("# Title\n\n**Bold** and `code`\n\n```json\n{}\n```");
    expect(plain).toContain("Title");
    expect(plain).toContain("Bold");
    expect(plain).not.toContain("```");
    expect(plain).toContain("{}");
  });

  it("does not re-export print helpers that pull KaTeX", () => {
    expect(Object.keys(markdownPlain).sort()).toEqual(
      ["markdownToCopyText", "markdownToPlainText", "markdownToSpeechText"].sort(),
    );
  });

  it("does not load printDocument", () => {
    jest.resetModules();
    jest.doMock("@/lib/printDocument", () => {
      throw new Error("markdownPlain must not import printDocument");
    });
    expect(() => require("@/lib/markdownPlain")).not.toThrow();
    jest.dontMock("@/lib/printDocument");
  });

  it("keeps the visible final answer and flattens pipe tables", () => {
    const src =
      "Intro\n\n```answer\n42\n```\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n";
    const copy = markdownToCopyText(src);
    const spoken = markdownToSpeechText(src);
    expect(copy).toContain("Intro");
    expect(copy).toContain("42");
    expect(copy).not.toContain("```");
    expect(copy).toContain("A — B");
    expect(copy).toContain("1 — 2");
    expect(spoken).toContain("42");
  });

  it("keeps code syntax, identifiers, and currency on Copy", () => {
    const src = [
      "user_id = {\"count\": 2}",
      "",
      "```python",
      "print(user_id * 2)",
      "```",
      "",
      "Costs $5 or $10.",
    ].join("\n");
    const copy = markdownToCopyText(src);
    expect(copy).toContain('user_id = {"count": 2}');
    expect(copy).toContain("print(user_id * 2)");
    expect(copy).toContain("Costs $5 or $10.");
    expect(copy).not.toContain("userid");
  });

  it("does not strip a numeric-only answer fence", () => {
    expect(markdownToCopyText("```answer\n42\n```")).toBe("42");
    expect(markdownToSpeechText("```answer\n42\n```")).toBe("42");
  });

  it("labels a chart for speech and omits chart JSON from Copy", () => {
    const src = 'Rainfall\n\n```chart\n{"mark":"bar"}\n```\n';
    expect(markdownToCopyText(src)).toBe("Rainfall");
    expect(markdownToSpeechText(src)).toContain("Rainfall");
    expect(markdownToSpeechText(src)).toContain("a chart");
    expect(markdownToCopyText(src)).not.toContain("mark");
  });

  it("never copies or speaks reminder control JSON", () => {
    const src = 'Done.\n\n```reminder\n{"title":"Pay rent"}\n```\n';
    expect(markdownToCopyText(src)).toBe("Done.");
    expect(markdownToSpeechText(src)).toBe("Done.");
    expect(markdownToCopyText(src)).not.toContain("Pay rent");
  });

  it("preserves ordered markers and nested indentation when copying", () => {
    const src = [
      "1. Open Settings",
      "2. Choose Privacy",
      "   - Disable analytics",
      "   - Keep crash reports",
    ].join("\n");
    const copy = markdownToCopyText(src);
    expect(copy).toContain("1. Open Settings");
    expect(copy).toContain("2. Choose Privacy");
    expect(copy).toContain("   • Disable analytics");
    expect(copy).toContain("   • Keep crash reports");
  });
});

describe("markdownToStructuredPrintHtml", () => {
  it("keeps code fences as pre blocks", () => {
    const html = markdownToStructuredPrintHtml("Note", "Intro\n\n```js\nconst x = 1;\n```\n\nDone");
    expect(html).toContain("<pre><code");
    expect(html).toContain("const x = 1;");
    expect(html).toContain("<p>Intro</p>");
    expect(html).toContain("<p>Done</p>");
  });

  it("renders headings and lists", () => {
    const html = markdownToStructuredPrintHtml(
      "Guide",
      "## Section\n\n- one\n- two\n\n1. first\n2. second",
    );
    expect(html).toContain("<h3>Section</h3>");
    expect(html).toContain("<ul>");
    expect(html).toContain("<li>one</li>");
    expect(html).toContain("<ol>");
    expect(html).toContain("<li>first</li>");
  });

  it("renders math fences with KaTeX instead of raw pre blocks", () => {
    const html = markdownToStructuredPrintHtml(
      "Math",
      "Answer:\n\n```math\nx^2 + 1 = 0\n```\n",
    );
    expect(html).toContain("katex");
    expect(html).toContain("math-block");
    expect(html).not.toContain("<pre><code class=\"language-math\"");
  });

  it("renders inline $math$ with KaTeX", () => {
    const html = markdownToStructuredPrintHtml("Inline", "Solve $x^2=4$ next.");
    expect(html).toContain("katex");
    expect(html).toContain("math-inline");
    expect(html).not.toContain("$x^2=4$");
  });

  it("converts $$ block math via preprocess before printing", () => {
    const html = markdownToStructuredPrintHtml("Display", "See\n\n$$\\frac{a}{b}$$\n");
    expect(html).toContain("katex");
    expect(html).toContain("math-block");
  });

  it("keeps hyphenated fence langs and prints GFM tables plus links", () => {
    const html = markdownToStructuredPrintHtml(
      "Note",
      "See [docs](https://example.com).\n\n```vega-lite\n{}\n```\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n",
    );
    expect(html).toContain('class="language-vega-lite"');
    expect(html).toContain('<a href="https://example.com">docs</a>');
    expect(html).toContain("<table>");
    expect(html).toContain("<th>A</th>");
    expect(html).toContain("<td>1</td>");
  });
});

function item(partial: Partial<ProjectItem> & Pick<ProjectItem, "id" | "content">): ProjectItem {
  return {
    list_title: "General",
    note: null,
    definition: null,
    example_sentence: null,
    status: "new",
    mastered: false,
    mastered_at: null,
    last_reviewed_at: null,
    review_count: 0,
    pronunciation_url: null,
    created_at: "2026-01-01T00:00:00Z",
    ...partial,
  };
}

describe("projectLearningToPrintHtml", () => {
  const labels = {
    mastered: "Mastered",
    learning: "Still learning",
    new: "New",
    empty: "No saved items yet.",
    definition: "Definition",
    example: "Example",
    topic: "Topic",
    summary: ({ total, mastered, learning, newCount }: {
      total: number;
      mastered: number;
      learning: number;
      newCount: number;
    }) => `${total} · ${mastered}/${learning}/${newCount}`,
  };

  it("groups vocab words by status with definitions", () => {
    const project = {
      id: "p1",
      title: "English",
      description: null,
      kind: "language",
      target_language: "en",
      native_language: null,
      level: "level2",
      daily_goal: 5,
      archived: false,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      mastered_count: 1,
      total_count: 3,
      stats: {
        total: 3,
        new_count: 1,
        learning_count: 1,
        mastered_count: 1,
        added_this_week: 0,
        due_for_review: 0,
        mastered_today: 0,
        pending_today: 0,
      },
      daily_history: [],
      daily_items_by_date: {},
      lists: [
        {
          list_title: "General",
          items: [
            item({
              id: "1",
              content: "ephemeral",
              status: "mastered",
              mastered: true,
              definition: "lasting a short time",
              example_sentence: "Fame is ephemeral.",
            }),
            item({
              id: "2",
              content: "ubiquitous",
              status: "learning",
              definition: "found everywhere",
            }),
            item({ id: "3", content: "serendipity", status: "new" }),
          ],
        },
      ],
    } as ProjectDetail;

    const html = projectLearningToPrintHtml(project, labels);
    expect(html).toContain("English");
    expect(html).toContain("Mastered (1)");
    expect(html).toContain("ephemeral");
    expect(html).toContain("lasting a short time");
    expect(html).toContain("Fame is ephemeral.");
    expect(html).toContain("Still learning (1)");
    expect(html).toContain("ubiquitous");
    expect(html).toContain("New (1)");
    expect(html).toContain("serendipity");
  });

  it("includes language project labels", () => {
    const project = {
      id: "p2",
      title: "Spanish",
      description: "Family, Food",
      kind: "language",
      target_language: "en",
      native_language: null,
      level: "level1",
      daily_goal: 10,
      archived: false,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      mastered_count: 1,
      total_count: 1,
      stats: {
        total: 1,
        new_count: 0,
        learning_count: 0,
        mastered_count: 1,
        added_this_week: 0,
        due_for_review: 0,
        mastered_today: 0,
        pending_today: 0,
      },
      daily_history: [],
      daily_items_by_date: {},
      lists: [
        {
          list_title: "History",
          items: [
            item({
              id: "q1",
              content: "Which treaty ended World War I?",
              status: "mastered",
              mastered: true,
              list_title: "History",
              definition: "Treaty of Versailles",
            }),
          ],
        },
      ],
    } as ProjectDetail;

    const html = projectLearningToPrintHtml(project, labels);
    expect(html).toContain("Language");
    expect(html).toContain("Which treaty ended World War I?");
    expect(html).toContain("Topic:");
    expect(html).toContain("History");
    expect(html).toContain("Treaty of Versailles");
  });
});
