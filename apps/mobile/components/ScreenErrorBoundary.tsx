import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { type ErrorBoundaryProps, useSegments } from "expo-router";

import { reportBoundaryError } from "@/lib/sentry";
import { StateView } from "@/ui/feedback/StateView";

function asError(thrown: unknown): Error {
  return thrown instanceof Error ? thrown : new Error(String(thrown));
}

/**
 * What a screen that threw while it rendered shows instead, under its own
 * header: a route exports it as `ErrorBoundary` and Expo Router draws it in
 * the screen's place, so the drawer, the chat and every other screen go on
 * working. Before, a crash in Settings, Memory, To-do or the Library reached
 * the root boundary and took the whole app with it, unreported. Try again
 * draws the screen afresh; each crash is reported once.
 */
export function ScreenErrorBoundary({ error, retry }: ErrorBoundaryProps) {
  const { t } = useTranslation();
  const segments = useSegments();
  // The route that crashed: segments follow whatever opens over this view later.
  const [screen] = useState(() => segments.join("/"));

  // Once per crash: the view draws again as the app around it changes, and
  // Try again unmounts it (a new crash is a new error).
  useEffect(() => {
    reportBoundaryError("screen", asError(error), null, screen);
  }, [error, screen]);

  return (
    <StateView
      variant="error"
      title={t("common.screen_error_title")}
      message={t("common.screen_error_body")}
      onRetry={() => void retry()}
      retryLabel={t("common.try_again")}
    />
  );
}
