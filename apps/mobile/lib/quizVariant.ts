export type QuizVariant = "vocab" | "trivia";

export function quizVariantForProjectKind(kind: string | undefined): QuizVariant {
  return kind === "trivia" ? "trivia" : "vocab";
}
