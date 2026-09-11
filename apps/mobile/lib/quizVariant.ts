export type QuizVariant = "vocab" | "trivia";

export function quizVariantForLearningKind(kind: string | undefined): QuizVariant {
  return "vocab";
}
