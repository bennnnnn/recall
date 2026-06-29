import {
  cacheDirectory,
  createDownloadResumable,
} from "expo-file-system/legacy";
import { Platform, Share } from "react-native";

function safeFileName(name: string, fallback: string): string {
  const cleaned = name.replace(/[^\w.-]+/g, "_").replace(/^_+|_+$/g, "");
  return cleaned || fallback;
}

async function downloadRemoteToCache(
  uri: string,
  token: string | null,
  fileName: string,
): Promise<string> {
  const dir = cacheDirectory;
  if (!dir) throw new Error("Storage unavailable.");

  const dest = `${dir}${fileName}`;
  const headers =
    token && uri.includes("/attachments/")
      ? { Authorization: `Bearer ${token}` }
      : undefined;

  const task = createDownloadResumable(uri, dest, { headers });
  const result = await task.downloadAsync();
  if (!result?.uri) throw new Error("Download failed.");
  return result.uri;
}

/** Download (or reuse local URI) then open the system share sheet to save or export. */
export async function downloadChatAttachment(options: {
  uri: string;
  token?: string | null;
  fileName?: string;
}): Promise<void> {
  const { uri, token = null, fileName = "attachment.jpg" } = options;
  const safeName = safeFileName(fileName, `recall-${Date.now()}.jpg`);

  let localUri = uri;
  if (uri.startsWith("http://") || uri.startsWith("https://")) {
    localUri = await downloadRemoteToCache(uri, token, safeName);
  }

  await Share.share(
    Platform.OS === "ios"
      ? { url: localUri, title: safeName }
      : { message: localUri, title: safeName },
  );
}
