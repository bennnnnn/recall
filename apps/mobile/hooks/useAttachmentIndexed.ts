import { useEffect, useState } from "react";

import { useAuthToken } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

const INDEX_POLL_MS = 2000;
const INDEX_POLL_MAX_MS = 60_000;

/** True once attachment RAG chunks exist (or indexing does not apply). */
export function useAttachmentIndexed(attachmentId: string | null | undefined): boolean {
  const token = useAuthToken();
  const [result, setResult] = useState({ attachmentId, token, indexed: !attachmentId });

  useEffect(() => {
    if (!attachmentId || !token) {
      setResult({ attachmentId, token, indexed: !attachmentId });
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
          setResult({ attachmentId, token, indexed: true });
          return;
        }
        setResult({ attachmentId, token, indexed: false });
      } catch {
        if (cancelled) return;
        setResult({ attachmentId, token, indexed: false });
      }
      if (Date.now() - started >= INDEX_POLL_MAX_MS) return;
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

  return !attachmentId || (result.attachmentId === attachmentId && result.token === token && result.indexed);
}
