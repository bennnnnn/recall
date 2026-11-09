import { useCallback } from "react";
import { useTranslation } from "react-i18next";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import type { FailureReporter } from "@/lib/cache/sessionResource";
import { reportRecoverableWarning } from "@/lib/reportRecoverableError";
import { useLatestRef } from "@/lib/latestRef";

/**
 * The warning toast for a failed read whose older rows stay on screen. The
 * cache decides when to call it (never for offline or sign-out); it stays
 * stable so passing it never re-runs a load effect.
 */
export function useReadFailureReport(): FailureReporter {
  const feedback = useActionFeedbackOptional();
  const { t } = useTranslation();
  const warn = () => reportRecoverableWarning(feedback, t("common.error"));
  const latest = useLatestRef(warn);
  return useCallback(() => latest.current(), [latest]);
}
