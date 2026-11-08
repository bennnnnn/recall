import { Platform, Share } from "react-native";

import { isShareCancelled } from "@/lib/shareCancelled";

/**
 * Android hands shared text to the next app inside the share intent, which crosses the
 * 1 MB Binder buffer (two bytes a character, shared by the whole app): a very long chat
 * failed as "Could not share this chat". Past this many characters it goes as a file.
 */
const ANDROID_TEXT_MAX_CHARS = 100_000;

/**
 * The text as `title.txt`, in a share folder of its own that a later share sweeps once old
 * (the app it went to may still be reading it), handed to the share sheet as a file. The
 * file system loads only for this: a text share needs none.
 */
async function shareAsTextFile(text: string, title: string): Promise<void> {
  const [fs, files, { shareLocalFile }] = await Promise.all([
    import("expo-file-system/legacy"),
    import("@/lib/accountFiles"),
    import("@/lib/shareFile"),
  ]);
  if (!fs.cacheDirectory) throw new Error("share_no_cache");
  await files.sweepAccountFolders("share", files.SHARE_COPY_MAX_AGE_MS);
  const folder = files.newAccountFolder("share");
  await fs.makeDirectoryAsync(folder, { intermediates: true });
  const file = files.fileInFolder(folder, files.documentFileName(title, "txt"));
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
