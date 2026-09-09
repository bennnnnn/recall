import { useEffect, useState } from "react";

import { useAuthToken } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

const INDEX_POLL_MS = 2000;
export const INDEX_POLL_MAX_MS = 60_000;

export type AttachmentIndexStatus = {
  indexed: boolean;
  failed: boolean;
};

/** Indexed once attachment RAG chunks exist (or indexing does not apply). */
export function useAttachmentIndexed(
  attachmentId: string | null | undefined,
): AttachmentIndexStatus {
  const token = useAuthToken();
  const [result, setResult] = useState({
    attachmentId,
    token,
    indexed: !attachmentId,
    failed: false,
  });

  useEffect(() => {
    if (!attachmentId || !token) {
      setResult({ attachmentId, token, indexed: !attachmentId, failed: false });
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const started = Date.now();

    const poll = async () => {
      try {
        const row = await api.getAttachmentUrl(token, attachmentId);
        if (cancelled) return;
        if (row.indexed !== false) {
          setResult({ attachmentId, token, indexed: true, failed: false });
          return;
        }
        setResult({ attachmentId, token, indexed: false, failed: false });
      } catch {
        if (cancelled) return;
        setResult({ attachmentId, token, indexed: false, failed: false });
      }
      if (Date.now() - started >= INDEX_POLL_MAX_MS) {
        if (!cancelled) {
          setResult({ attachmentId, token, indexed: false, failed: true });
        }
        return;
      }
      timer = setTimeout(() => {
        void poll();
      }, INDEX_POLL_MS);
    };
    void poll();
    return () => {
      cancelled = true;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [attachmentId, token]);

  if (!attachmentId) {
    return { indexed: true, failed: false };
  }
  if (result.attachmentId !== attachmentId || result.token !== token) {
    return { indexed: false, failed: false };
  }
  return { indexed: result.indexed, failed: result.failed };
}
