import { Platform } from "react-native";

import { receiveOpenedDocument } from "@/features/attachments/model/openedDocument";

/** A file's URL: iOS hands Recall `file:` (Open in, the share sheet), Android `content:` (Open with). */
const FILE_URL = /^(?:file|content):/i;

/**
 * Expo Router hands every URL the system opens Recall with to `app/+native-intent.tsx`
 * before it routes it. A file another app opened in Recall is no route (it would land on
 * +not-found): on iOS the file is held for New chat (openedDocument.ts; only iOS itself
 * opens an app with a `file:` URL, its Inbox copy), a launch opens on the chat, and a
 * running app stays where it is until the chat takes the file
 * (features/chat/components/OpenedDocumentBootstrap.tsx). Android's Open with and Share are
 * read by modules/opened-document, which also gives the file's name and refuses a URI that
 * would read Recall's own files, so a URL here is only kept off the router. Every other URL
 * routes as it came.
 */
export function redirectSystemPath({ path, initial }: { path: string; initial: boolean }): string | null {
  if (!FILE_URL.test(path)) return path;
  try {
    if (Platform.OS === "ios" && /^file:/i.test(path)) receiveOpenedDocument(path);
  } catch (error) {
    // The chat opens without the file rather than the app failing to start.
    console.warn("[openedFile]", { stage: "receive", error: error instanceof Error ? error.name : typeof error });
  }
  return initial ? "/" : null;
}
