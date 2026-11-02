import { useCallback, type MutableRefObject } from "react";

import type { PendingAttachment } from "@/features/attachments/model/attachments";
import {
  composerTextAfterSubjectScan,
  type ScannerSubject,
} from "@/lib/scanner/subjects";

type Options = {
  /** The composer's live text; a scan keeps what the student had typed. */
  inputRef: MutableRefObject<string>;
  setInput: (text: string) => void;
  /** Puts the scan's photo in the composer, freeing the file it replaces. */
  replacePendingAttachment: (next: PendingAttachment | null) => void;
  setMathScannerOpen: (open: boolean) => void;
  handleSend: (overrideText?: string) => Promise<unknown>;
};

/**
 * What the scanner hands the composer: the cropped photo, sent at once with its tab's
 * caption. The caption names the subject, and the turn reads the problem off the photo
 * and solves it (the API's subject photo readers); a read that finds nothing is an
 * ordinary photo turn. The photo always goes, so the model sees any diagram.
 */
export function useMathScanSend({
  inputRef,
  setInput,
  replacePendingAttachment,
  setMathScannerOpen,
  handleSend,
}: Options) {
  const handleMathScanCaptured = useCallback((pending: PendingAttachment, subject: ScannerSubject) => {
    replacePendingAttachment(pending);
    const text = composerTextAfterSubjectScan(inputRef.current, subject);
    setInput(text);
    setMathScannerOpen(false);
    void handleSend(text);
  }, [handleSend, setInput, replacePendingAttachment, setMathScannerOpen, inputRef]);

  return { handleMathScanCaptured };
}
