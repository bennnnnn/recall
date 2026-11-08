import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { reportRecoverableWarning } from "@/lib/reportRecoverableError";
import { shareOneAtATime } from "@/lib/shareFile";
import { ShareInProgressError } from "@/lib/shareUnavailable";

/**
 * A Share button's press and its busy state: busy from the tap, through any download, until
 * the sheet closes. A press while any file share runs is not tried (`shareOneAtATime`) and
 * says so in a toast; any other failure is thrown to the caller, which says what went wrong.
 */
export function useFileShare(): { sharing: boolean; share: (task: () => Promise<void>) => Promise<void> } {
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const [sharing, setSharing] = useState(false);
  const share = useCallback(async (task: () => Promise<void>) => {
    try {
      await shareOneAtATime(async () => {
        setSharing(true);
        try {
          await task();
        } finally {
          setSharing(false);
        }
      });
    } catch (error) {
      if (!(error instanceof ShareInProgressError)) throw error;
      reportRecoverableWarning(feedback, t("common.share_in_progress"));
    }
  }, [feedback, t]);
  return { sharing, share };
}
