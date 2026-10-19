import { useCallback, useRef, useState, type MutableRefObject } from "react";
import { Keyboard, Linking } from "react-native";

import type { ActionFeedbackApi } from "@/contexts/actionFeedbackCore";
import type { AttachmentSource } from "@/features/attachments/components/AttachmentSourceSheet";
import {
  HeicUnsupportedError,
  NativePickerBusyError,
  NativePickerTimeoutError,
  PhotoLibraryPermissionError,
  pickDocument,
  pickFromCamera,
  pickFromPhotoLibrary,
  type PendingAttachment,
} from "@/features/attachments/model/attachments";
import { getSessionGeneration } from "@/lib/auth";
import { reportRecoverableWarning } from "@/lib/reportRecoverableError";

type Options = {
  token: string | null;
  streaming: boolean;
  /** Account generation the composer was rendered for. */
  session: number;
  /** Bumped on every thread or account switch: a pick that outlives its view is dropped. */
  viewRef: MutableRefObject<{ version: number }>;
  /** A send is preparing; the composer takes no new attachment until it settles. */
  sendInFlightRef: MutableRefObject<boolean>;
  setPendingAttachment: (value: PendingAttachment | null) => void;
  feedback: ActionFeedbackApi | null;
  t: (key: string) => string;
};

/** The composer's attach sheet and math scanner: which is open, and the pick each source runs. */
export function useComposerAttachmentSheet({
  token,
  streaming,
  session,
  viewRef,
  sendInFlightRef,
  setPendingAttachment,
  feedback,
  t,
}: Options) {
  const [attachSheetOpen, setAttachSheetOpen] = useState(false);
  const [mathScannerOpen, setMathScannerOpen] = useState(false);
  const attachPickInFlightRef = useRef(false);

  const handlePickAttachment = useCallback(() => {
    if (!token || streaming || sendInFlightRef.current || attachPickInFlightRef.current) return;
    Keyboard.dismiss();
    // Let the keyboard finish dismissing so the first tap isn't swallowed on Android.
    const version = viewRef.current.version;
    requestAnimationFrame(() => {
      if (viewRef.current.version === version && session === getSessionGeneration()) setAttachSheetOpen(true);
    });
  }, [token, streaming, session, viewRef, sendInFlightRef]);

  const handleAttachmentSheetSelect = useCallback(
    async (source: AttachmentSource) => {
      if (
        attachPickInFlightRef.current ||
        !token ||
        streaming ||
        sendInFlightRef.current
      )
        return;
      const version = viewRef.current.version;
      const current = () => viewRef.current.version === version && session === getSessionGeneration();
      attachPickInFlightRef.current = true;
      setAttachSheetOpen(false);

      if (!current() || !token || streaming || sendInFlightRef.current) {
        attachPickInFlightRef.current = false;
        return;
      }

      try {
        if (source === "solve_math_camera") {
          setMathScannerOpen(true);
          return;
        }
        const picked =
          source === "camera"
            ? await pickFromCamera()
            : source === "photo"
              ? await pickFromPhotoLibrary()
              : await pickDocument();
        if (picked && current()) {
          setPendingAttachment(picked);
        }
      } catch (error) {
        if (!current()) return;
        if (error instanceof HeicUnsupportedError) {
          reportRecoverableWarning(feedback, t("chat.heic_unsupported_body"));
        } else if (error instanceof PhotoLibraryPermissionError) {
          if (error.needsSettings) void Linking.openSettings();
          feedback?.error(t("chat.photos_permission"));
        } else if (
          error instanceof NativePickerBusyError ||
          error instanceof NativePickerTimeoutError
        ) {
          feedback?.error(t("chat.picker_busy"));
        } else {
          feedback?.error(
            error instanceof Error ? error.message : t("chat.attach_failed"),
          );
        }
      } finally {
        attachPickInFlightRef.current = false;
      }
    },
    [feedback, session, streaming, t, token, setPendingAttachment, viewRef, sendInFlightRef],
  );

  return {
    attachSheetOpen,
    setAttachSheetOpen,
    mathScannerOpen,
    setMathScannerOpen,
    attachPickInFlightRef,
    handlePickAttachment,
    handleAttachmentSheetSelect,
  };
}
