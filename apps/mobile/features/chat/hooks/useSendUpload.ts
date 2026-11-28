import { useSyncExternalStore } from "react";

import { type SendUpload, sendUploadStore } from "@/features/chat/model/sendUpload";

/** The chat send's upload under way (its progress and Cancel), or null. */
export function useSendUpload(): SendUpload | null {
  return useSyncExternalStore(sendUploadStore.subscribe, sendUploadStore.get, sendUploadStore.get);
}
