import { deriveLessonStep } from "@/lib/lessonStep";
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

const checkInDump = `5. **Libro** — Book
*Example:* Estoy leyendo un libro.

---

### Check-In
Since you’re starting out, this **beginner level** focuses on high-frequency words.

### Let’s Begin!
Write your own sentence using **Hola**.`;

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
      expect(step.question).toBe("Which one is hello?");
    }
  });

  it("treats a vocab card as a card step and ignores surrounding markdown", () => {
    const step = deriveLessonStep([
      message(
        "assistant",
        '```vocab_card\n{"word":"hola","definition":"hello"}\n```\nWrite your own sentence with **hola**.',
      ),
    ]);
    expect(step.kind).toBe("vocab_card");
    if (step.kind === "vocab_card") {
      expect(step.card.word).toBe("hola");
    }
  });

  it("does not surface a check-in or markdown vocab dump as a lesson step", () => {
    const step = deriveLessonStep([message("assistant", checkInDump)]);
    expect(step.kind).toBe("loading");
  });

  it("uses the quiz fence question, not leftover assistant prose", () => {
    const step = deriveLessonStep([
      message("assistant", `### Let’s Begin!\n${quizFence}\nWrite a sentence.`),
    ]);
    expect(step.kind).toBe("quiz");
    if (step.kind === "quiz") {
      expect(step.question).toBe("Which one is hello?");
      expect(step.question).not.toContain("**");
      expect(step.question).not.toContain("Let’s Begin");
    }
  });
});
