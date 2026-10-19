import { useCallback, useRef, useState, type MutableRefObject } from "react";
import { Keyboard, Linking } from "react-native";

import type { AttachmentSource } from "@/features/attachments/components/AttachmentSourceSheet";
import { attachmentErrorMessage } from "@/features/attachments/model/attachmentErrors";
import {
  discardDraftAttachment,
  NativePickerBusyError,
  NativePickerTimeoutError,
  PhotoLibraryPermissionError,
  pickDocument,
  pickFromCamera,
  pickFromPhotoLibrary,
  type PendingAttachment,
} from "@/features/attachments/model/attachments";
import { getSessionGeneration } from "@/lib/auth";

type Feedback = { error: (message: string) => void } | null | undefined;

type Options = {
  token: string | null;
  streaming: boolean;
  session: number;
  /** Bumped whenever the composer moves to another thread or account. */
  viewRef: MutableRefObject<{ version: number }>;
  sendInFlightRef: MutableRefObject<boolean>;
  feedback: Feedback;
  t: (key: string, options?: Record<string, unknown>) => string;
  replacePendingAttachment: (next: PendingAttachment | null) => void;
  setAttachSheetOpen: (open: boolean) => void;
  setMathScannerOpen: (open: boolean) => void;
};

function pickFrom(source: Exclude<AttachmentSource, "solve_math_camera">) {
  if (source === "camera") return pickFromCamera();
  if (source === "photo") return pickFromPhotoLibrary();
  return pickDocument();
}

/**
 * The attach sheet and its pickers. A pick is "in flight" from the tap until
 * its photo is prepared (resized, re-encoded, size-checked), and Send waits:
 * a send that slipped in first went without the photo, which then turned up
 * afterwards as a stray draft.
 */
export function useComposerAttachmentPick({
  token,
  streaming,
  session,
  viewRef,
  sendInFlightRef,
  feedback,
  t,
  replacePendingAttachment,
  setAttachSheetOpen,
  setMathScannerOpen,
}: Options) {
  const [attachPicking, setAttachPicking] = useState(false);
  const attachPickInFlightRef = useRef(false);

  const handlePickAttachment = useCallback(() => {
    if (!token || streaming || sendInFlightRef.current || attachPickInFlightRef.current) return;
    Keyboard.dismiss();
    // Let the keyboard finish dismissing so the first tap isn't swallowed on Android.
    const version = viewRef.current.version;
    requestAnimationFrame(() => {
      if (viewRef.current.version === version && session === getSessionGeneration()) setAttachSheetOpen(true);
    });
  }, [token, streaming, session, viewRef, sendInFlightRef, setAttachSheetOpen]);

  const handleAttachmentSheetSelect = useCallback(
    async (source: AttachmentSource) => {
      if (attachPickInFlightRef.current || !token || streaming || sendInFlightRef.current) return;
      setAttachSheetOpen(false);
      if (source === "solve_math_camera") {
        setMathScannerOpen(true);
        return;
      }
      const version = viewRef.current.version;
      const current = () => viewRef.current.version === version && session === getSessionGeneration();
      attachPickInFlightRef.current = true;
      setAttachPicking(true);
      try {
        const picked = await pickFrom(source);
        // A pick that lands after the user moved on belongs to no composer.
        if (picked && current()) replacePendingAttachment(picked);
        else discardDraftAttachment(null, picked);
      } catch (error) {
        if (!current()) return;
        if (error instanceof PhotoLibraryPermissionError) {
          if (error.needsSettings) void Linking.openSettings();
          feedback?.error(t("chat.photos_permission"));
        } else if (error instanceof NativePickerBusyError || error instanceof NativePickerTimeoutError) {
          feedback?.error(t("chat.picker_busy"));
        } else {
          feedback?.error(attachmentErrorMessage(error, t));
        }
      } finally {
        attachPickInFlightRef.current = false;
        setAttachPicking(false);
      }
    },
    [token, streaming, session, viewRef, sendInFlightRef, feedback, t, replacePendingAttachment, setAttachSheetOpen, setMathScannerOpen],
  );

  return { attachPicking, attachPickInFlightRef, handlePickAttachment, handleAttachmentSheetSelect };
}
