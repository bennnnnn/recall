import { useEffect, useState } from "react";

import { useAuthToken } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

const INDEX_POLL_MS = 2000;
/** Match jobs.py `_JOB_DONE_CLAIM_TTL_SECONDS` (300s) plus one poll slack. */
export const INDEX_POLL_MAX_MS = 360_000;
/**
 * An attachment older than this has had its indexing job run (or give up),
 * so its first answer is final. Well past INDEX_POLL_MAX_MS so a phone clock
 * that runs a few minutes ahead never fails a fresh upload.
 */
const INDEX_SETTLED_AGE_MS = 15 * 60_000;

function settledByAge(createdAt: string | undefined): boolean {
  const created = createdAt ? Date.parse(createdAt) : Number.NaN;
  return Number.isFinite(created) && Date.now() - created >= INDEX_SETTLED_AGE_MS;
}

type AttachmentIndexStatus = {
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
        // A file with no extractable text stays unindexed forever. Without
        // this, every visit to an old chat polled it for six minutes.
        if (settledByAge(row.created_at)) {
          setResult({ attachmentId, token, indexed: false, failed: true });
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
