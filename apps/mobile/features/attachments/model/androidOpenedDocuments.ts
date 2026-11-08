import { requireOptionalNativeModule } from "expo-modules-core";

import { receiveOpenedDocument } from "@/features/attachments/model/openedDocument";
import type { OpenedFileInfo } from "@/features/attachments/model/openedDocumentCopy";

/**
 * What `modules/opened-document` reads from the intent: the file's URI, and from its provider,
 * off the JS thread, the name its app gave it, its size and its type.
 */
type NativeDocument = { uri?: unknown; name?: unknown; size?: unknown; type?: unknown };

function infoOf(document: NativeDocument): OpenedFileInfo {
  const { name, size, type } = document;
  return {
    ...(typeof name === "string" && name ? { name } : {}),
    ...(typeof size === "number" && Number.isFinite(size) && size >= 0 ? { size } : {}),
    ...(typeof type === "string" && type ? { type } : {}),
  };
}

type OpenedDocumentModule = {
  takeDocumentAsync: () => Promise<NativeDocument | null>;
  addListener: (event: "onDocument", listener: () => void) => { remove: () => void };
};

function loadModule(): OpenedDocumentModule | null {
  const native = requireOptionalNativeModule<Partial<OpenedDocumentModule>>("RecallOpenedDocument");
  return typeof native?.takeDocumentAsync === "function" && typeof native.addListener === "function"
    ? (native as OpenedDocumentModule)
    : null;
}

/**
 * Android hands Recall a PDF as a `content:` URI: as the intent's data for Open with
 * (ACTION_VIEW), and in EXTRA_STREAM for Share (ACTION_SEND), which React Native's Linking
 * never reads. `modules/opened-document` keeps the newest one until it is taken here (one
 * that launched Recall, then each that comes while it runs) and refuses a URI Recall's own
 * provider serves. iOS has no such module: its file comes as a URL (openedDocumentRoute.ts).
 * Neither has a build made before it, Expo Go included.
 */
export function watchAndroidOpenedDocuments(): () => void {
  const native = loadModule();
  if (!native) return () => undefined;
  const take = () => {
    native.takeDocumentAsync().then((document) => {
      if (typeof document?.uri !== "string" || !document.uri) return;
      receiveOpenedDocument(document.uri, infoOf(document));
    }, (error: unknown) => {
      // An intent the module could not read leaves the chat as it was.
      console.warn("[openedFile]", { stage: "take", error: error instanceof Error ? error.name : typeof error });
    });
  };
  const subscription = native.addListener("onDocument", take);
  take();
  return () => subscription.remove();
}
