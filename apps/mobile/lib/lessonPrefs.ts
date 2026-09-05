import { prefFilePath, readPrefFile, writePrefFile } from "@/lib/filePrefs";

export type LessonFontSize = "small" | "medium" | "large";

export type LessonPrefs = {
  effectSound: boolean;
  readWords: boolean;
  fontSize: LessonFontSize;
};

export const DEFAULT_LESSON_PREFS: LessonPrefs = {
  effectSound: true,
  readWords: false,
  fontSize: "medium",
};

const FILE_NAME = "recall.lesson-prefs.json";

let cached: LessonPrefs | null = null;

function filePath(): string | null {
  return prefFilePath(FILE_NAME);
}

export function lessonTextScale(size: LessonFontSize): number {
  if (size === "small") return 0.9;
  if (size === "large") return 1.18;
  return 1;
}

export function parseLessonPrefs(raw: string | null): LessonPrefs {
  if (!raw?.trim()) return { ...DEFAULT_LESSON_PREFS };
  try {
    const data = JSON.parse(raw) as Partial<LessonPrefs>;
    const fontSize: LessonFontSize =
      data.fontSize === "small" || data.fontSize === "large" ? data.fontSize : "medium";
    return {
      effectSound: data.effectSound !== false,
      readWords: data.readWords === true,
      fontSize,
    };
  } catch {
    return { ...DEFAULT_LESSON_PREFS };
  }
}

export async function getLessonPrefs(): Promise<LessonPrefs> {
  if (cached) return cached;
  cached = parseLessonPrefs(await readPrefFile(filePath()));
  return cached;
}

export async function setLessonPrefs(prefs: LessonPrefs): Promise<void> {
  cached = prefs;
  await writePrefFile(filePath(), JSON.stringify(prefs));
}

/** Test helper — reset in-memory cache between cases. */
export function resetLessonPrefsCache(): void {
  cached = null;
}
