import { Platform, Share } from "react-native";

import { isShareCancelled } from "@/lib/share/cancelled";

/**
 * Android hands shared text to the next app inside the share intent, which crosses the 1 MB
 * Binder buffer shared by the whole app, two bytes a character, and twice over: the intent
 * carries the text as EXTRA_TEXT and again in its ClipData. A very long chat failed as "Could
 * not share this chat". Past this many characters (about 200 KB in that one transaction, with
 * room for whatever else the app has in flight) it goes as a file.
 */
const ANDROID_TEXT_MAX_CHARS = 50_000;

/**
 * The text as `title.txt` in a share folder of its own (`newShareFile`), handed to the share
 * sheet as a file. The file system loads only for this: a text share needs none.
 */
async function shareAsTextFile(text: string, title: string): Promise<void> {
  const [fs, { documentFileName, newShareFile }, { shareLocalFile }] = await Promise.all([
    import("expo-file-system/legacy"),
    import("@/lib/accountFiles"),
    import("@/lib/share/file"),
  ]);
  const { file } = await newShareFile(documentFileName(title, "txt"));
  await fs.writeAsStringAsync(file, text, { encoding: fs.EncodingType.UTF8 });
  await shareLocalFile(file, { title, mimeType: "text/plain" });
}

/** Open the OS share sheet (Messages, Mail, Files, …). */
export async function presentShareSheet(options: {
  message: string;
  title?: string | null;
}): Promise<void> {
  const message = options.message.trim();
  if (!message) {
    throw new Error("share_empty");
  }
  const title = options.title?.trim() || undefined;
  if (Platform.OS === "android" && message.length > ANDROID_TEXT_MAX_CHARS) {
    await shareAsTextFile(message, title ?? "");
    return;
  }
  try {
    await Share.share(
      { message, ...(title ? { title } : {}) },
      Platform.OS === "ios"
        ? { subject: title }
        : { dialogTitle: title },
    );
  } catch (error) {
    if (isShareCancelled(error)) return;
    throw error;
  }
}
