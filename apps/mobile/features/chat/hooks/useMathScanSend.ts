import { useCallback, type MutableRefObject } from "react";

import type { PendingAttachment } from "@/features/attachments/model/attachments";
import type { ScanReading } from "@/lib/api";
import {
  composerTextAfterScanConfirm,
  type ReadBackSubject,
  scanSolveMessage,
} from "@/lib/scanner/readBack";
import {
  scanFailureDetail,
  scanFailureMessageKey,
  type ScanReadFailure,
} from "@/lib/scanner/scanReadError";
import {
  composerTextAfterSubjectScan,
  type ScannerSubject,
} from "@/lib/scanner/subjects";

type Options = {
  token: string | null;
  t: (key: string) => string;
  /** The composer's live text; a scan keeps what the student had typed. */
  inputRef: MutableRefObject<string>;
  setInput: (text: string) => void;
  setPendingAttachment: (value: PendingAttachment | null) => void;
  setMathScannerOpen: (open: boolean) => void;
  handleSend: (overrideText?: string) => Promise<void>;
};

/** What the math scanner hands the composer: a captured photo, a read-back, or a confirmed reading to solve. */
export function useMathScanSend({
  token,
  t,
  inputRef,
  setInput,
  setPendingAttachment,
  setMathScannerOpen,
  handleSend,
}: Options) {
  const handleMathScanCaptured = useCallback((
    pending: PendingAttachment,
    subject: ScannerSubject,
    confirmedReading?: string,
  ) => {
    setPendingAttachment(pending);
    // A checked reading rides with the photo so the API solves what the
    // student confirmed instead of reading the photo again.
    const text = confirmedReading
      ? withComposerDraft(composerTextAfterScanConfirm(confirmedReading, subject), inputRef.current)
      : composerTextAfterSubjectScan(inputRef.current, subject);
    setInput(text);
    setMathScannerOpen(false);
    void handleSend(text);
  }, [handleSend, setInput, setPendingAttachment, setMathScannerOpen, inputRef]);

  const readScan = useCallback(
    async (
      scan: PendingAttachment,
      subject: ReadBackSubject,
      signal: AbortSignal,
    ): Promise<ScanReading | ScanReadFailure | null> => {
      if (!token) return null;
      try {
        // Loaded on use: the API barrel pulls in native file-system modules
        // this hook otherwise never touches.
        const { api } = await import("@/lib/api");
        return await api.readScan(token, subject, scan, signal);
      } catch (error) {
        // Every subject names a missing reader, an oversized photo and a
        // limit the same way. Anything else stays generic.
        const detail = scanFailureDetail(error);
        if (!detail) return null;
        const key = scanFailureMessageKey(detail);
        return { error: key ? t(key) : detail };
      }
    },
    [t, token],
  );

  const handleMathScanSolve = useCallback((reading: string, subject: ScannerSubject = "math") => {
    setMathScannerOpen(false);
    const message = scanSolveMessage(reading, subject);
    if (!message) return;
    const text = withComposerDraft(message, inputRef.current);
    setInput(text);
    void handleSend(text);
  }, [handleSend, setInput, setMathScannerOpen, inputRef]);

  return { handleMathScanCaptured, readScan, handleMathScanSolve };
}

/** Keep what the student had already typed, after the scan's own text. */
function withComposerDraft(text: string, draft: string): string {
  const kept = draft.trim();
  return kept ? `${text}\n\n${kept}` : text;
}
