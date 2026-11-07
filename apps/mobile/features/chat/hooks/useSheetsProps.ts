import { useMemo } from "react";

import type { ChatScreenSheetsProps } from "@/features/chat/components/ChatScreenBody";

/** The sheets the chat opens over its thread (attach, scanner, paywall), kept as one value. */
export function useSheetsProps(sheets: ChatScreenSheetsProps): ChatScreenSheetsProps {
  const {
    attachSheetOpen,
    onCloseAttachSheet,
    attachSheetLift,
    onAttachmentSource,
    mathScannerOpen,
    onCloseMathScanner,
    onMathScanCaptured,
    upgradeVisible,
    upgradeSource,
    onCloseUpgrade,
  } = sheets;
  return useMemo(
    () => ({
      attachSheetOpen,
      onCloseAttachSheet,
      attachSheetLift,
      onAttachmentSource,
      mathScannerOpen,
      onCloseMathScanner,
      onMathScanCaptured,
      upgradeVisible,
      upgradeSource,
      onCloseUpgrade,
    }),
    [
      attachSheetOpen,
      onCloseAttachSheet,
      attachSheetLift,
      onAttachmentSource,
      mathScannerOpen,
      onCloseMathScanner,
      onMathScanCaptured,
      upgradeVisible,
      upgradeSource,
      onCloseUpgrade,
    ],
  );
}
