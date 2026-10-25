import { useEffect, useState } from "react";
import { StyleSheet, View } from "react-native";
import { useTranslation } from "react-i18next";
import { type ErrorBoundaryProps, useSegments } from "expo-router";

import { reportBoundaryError } from "@/lib/sentry";
import { useTheme } from "@/lib/theme";
import { StateView } from "@/ui/feedback/StateView";

function asError(thrown: unknown): Error {
  return thrown instanceof Error ? thrown : new Error(String(thrown));
}

/**
 * What a screen that threw while it rendered shows instead: a route or a
 * layout exports it as `ErrorBoundary` and Expo Router draws it in that
 * route's place. Todos and the Library catch their own crash under their
 * header; Settings and Memory catch any page's on their stack layout, so the
 * drawer, the chat and every other screen go on working. The app's root
 * layout exports it too, for the chat and the sign-in flow: there it stands in
 * for the whole app. Try again draws the screen afresh; each crash is reported
 * once.
 */
export function ScreenErrorBoundary({ error, retry }: ErrorBoundaryProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const segments = useSegments();
  // The route that crashed: segments follow whatever opens over this view later.
  // The chat's are empty; its file is `index`.
  const [screen] = useState(() => segments.join("/") || "index");

  // Once per crash: the view draws again as the app around it changes, and
  // Try again unmounts it (a new crash is a new error).
  useEffect(() => {
    reportBoundaryError("screen", asError(error), null, screen);
  }, [error, screen]);

  return (
    // At the root no stack paints the page behind it.
    <View style={[s.page, { backgroundColor: theme.bg }]} testID="screen-error">
      <StateView
        variant="error"
        title={t("common.screen_error_title")}
        message={t("common.screen_error_body")}
        onRetry={() => void retry()}
        retryLabel={t("common.try_again")}
      />
    </View>
  );
}

const s = StyleSheet.create({
  page: { flex: 1 },
});
