/** What the user picked on a quiz card, and whether they checked it. */
export type QuizAttempt = { picked: number | null; checked: boolean };

// The answer stays picked when the list recycles the message off screen and back.
const attempts = new Map<string, QuizAttempt>();

export function quizAttempt(content: string): QuizAttempt | undefined {
  return attempts.get(content);
}

export function saveQuizAttempt(content: string, attempt: QuizAttempt): void {
  attempts.set(content, attempt);
}

/** Sign-out: the next account starts with every quiz unanswered. */
export function clearQuizAttempts(): void {
  attempts.clear();
}
