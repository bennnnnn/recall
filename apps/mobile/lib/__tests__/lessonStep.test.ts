import { deriveLessonStep, looksLikeOpenEndedPrompt } from "@/lib/lessonStep";
import type { Message } from "@/lib/api";

function message(role: Message["role"], content: string, id = "1"): Message {
  return {
    id,
    role,
    content,
    model: null,
    created_at: new Date().toISOString(),
  };
}

const quizFence = `\`\`\`vocab_quiz
{"word":"hello","question":"Which one is hello?","correct":"B","choices":[{"letter":"A","text":"goodbye"},{"letter":"B","text":"hello"},{"letter":"C","text":"thanks"},{"letter":"D","text":"please"}]}
\`\`\``;

describe("deriveLessonStep", () => {
  it("keeps the original quiz after a hint-only wrong answer", () => {
    const step = deriveLessonStep([
      message("user", "Continue Spanish", "u1"),
      message("assistant", quizFence, "a1"),
      message("user", "A", "u2"),
      message("assistant", "Not quite — think greeting.", "a2"),
    ]);
    expect(step.kind).toBe("quiz");
    if (step.kind === "quiz") {
      expect(step.quiz.correct).toBe("B");
      expect(step.messageId).toBe("a1");
    }
  });

  it("treats a vocab card plus write-a-sentence prompt as a card step", () => {
    const step = deriveLessonStep([
      message(
        "assistant",
        '```vocab_card\n{"word":"hola","definition":"hello"}\n```\nWrite your own sentence with **hola**.',
      ),
    ]);
    expect(step.kind).toBe("vocab_card");
    if (step.kind === "vocab_card") {
      expect(step.card.word).toBe("hola");
      expect(step.prompt).toContain("Write your own sentence");
    }
  });
});

describe("looksLikeOpenEndedPrompt", () => {
  it("detects teach-to-use prompts", () => {
    expect(looksLikeOpenEndedPrompt("Write your own sentence with serendipity.")).toBe(true);
    expect(looksLikeOpenEndedPrompt("Nice work today.")).toBe(false);
  });
});
