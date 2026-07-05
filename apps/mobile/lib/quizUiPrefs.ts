import * as SecureStore from "expo-secure-store";

export type QuizUiStyle = "card" | "simple";

const KEY = "quiz_ui_style";

let cachedStyle: QuizUiStyle | null = null;
let prefResolved = false;

export function isQuizUiPrefResolved(): boolean {
  return prefResolved;
}

export async function getQuizUiStyle(): Promise<QuizUiStyle | null> {
  if (cachedStyle !== null) return cachedStyle;
  try {
    const raw = await SecureStore.getItemAsync(KEY);
    if (raw === "card" || raw === "simple") {
      cachedStyle = raw;
      prefResolved = true;
      return raw;
    }
  } catch {
    /* fall through */
  }
  return null;
}

export async function setQuizUiStyle(style: QuizUiStyle): Promise<void> {
  cachedStyle = style;
  prefResolved = true;
  await SecureStore.setItemAsync(KEY, style);
}

/** Test helper — reset in-memory cache between cases. */
export function resetQuizUiPrefCache(): void {
  cachedStyle = null;
  prefResolved = false;
}
