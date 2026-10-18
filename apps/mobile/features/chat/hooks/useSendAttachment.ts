import { useCallback, useRef, useState, type SetStateAction } from "react";

import { uploadChatAttachment, type PendingAttachment } from "@/features/attachments/model/attachments";

/** The attachment queued in the composer. A send in flight reads the ref, which never lags a render. */
export function useSendAttachment() {
  const [pendingAttachment, setPendingAttachmentState] = useState<PendingAttachment | null>(null);
  const pendingAttachmentRef = useRef<PendingAttachment | null>(null);
  const setPendingAttachment = useCallback((value: SetStateAction<PendingAttachment | null>) => {
    const next = typeof value === "function" ? value(pendingAttachmentRef.current) : value;
    pendingAttachmentRef.current = next;
    setPendingAttachmentState(next);
  }, []);
  return { pendingAttachment, pendingAttachmentRef, setPendingAttachment };
}

/** Uploads once: the copy it returns carries the server id, so a restore or a retry reuses it. */
export async function uploadSendAttachment(token: string, attachment: PendingAttachment) {
  const id = await uploadChatAttachment(token, attachment);
  return { ids: [id], attachment: { ...attachment, existingAttachmentId: id } };
}
