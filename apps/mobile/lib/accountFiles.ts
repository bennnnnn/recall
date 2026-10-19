import { cacheDirectory, deleteAsync, readDirectoryAsync } from "expo-file-system/legacy";

/**
 * Files in the cache directory that hold one account's content. Each writer names
 * its file with its prefix here, so sign-out can find every one, including those
 * left by an earlier app run.
 */
export const ACCOUNT_FILE_PREFIX = {
  /** Settings → Data controls: the whole account export (chats, memories). */
  export: "recall-export-",
  /** A chat's HTML opened in the system browser. */
  htmlPreview: "recall-preview-",
  /** A reply read aloud; deleted after it plays, unless the app stopped first. */
  speech: "recall-tts-",
} as const;

/** expo-print writes every PDF (chat exports) here, on iOS and Android alike. */
const PRINTED_PDF_DIRECTORY = "Print/";

const PREFIXES: readonly string[] = Object.values(ACCOUNT_FILE_PREFIX);

async function filesIn(directory: string): Promise<string[]> {
  return readDirectoryAsync(directory).catch(() => [] as string[]);
}

/** Sign-out: delete every file above, so nothing of this account stays on the phone. */
export async function deleteAccountFiles(): Promise<void> {
  const cache = cacheDirectory;
  if (!cache) return;
  const pdfs = `${cache}${PRINTED_PDF_DIRECTORY}`;
  const [names, printed] = await Promise.all([filesIn(cache), filesIn(pdfs)]);
  const paths = [
    ...names.filter((name) => PREFIXES.some((prefix) => name.startsWith(prefix))).map((name) => `${cache}${name}`),
    ...printed.filter((name) => name.toLowerCase().endsWith(".pdf")).map((name) => `${pdfs}${name}`),
  ];
  await Promise.allSettled(paths.map((path) => deleteAsync(path, { idempotent: true })));
}
