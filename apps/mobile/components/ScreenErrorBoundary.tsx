import { useContext, useEffect, useState } from "react";
import { StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";
import { type ErrorBoundaryProps, useSegments } from "expo-router";
import { HeaderShownContext, NavigationContext } from "expo-router/react-navigation";

import { reportBoundaryError } from "@/lib/sentry";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";
import { StackBackButton } from "@/ui/controls/StackBackButton";
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
 *
 * A section's view has no header (its stack went with the crash), so when
 * there is a screen to go back to it gets the back arrow where the Settings
 * home draws its own. The root's never does: no screen is left under it.
 */
export function ScreenErrorBoundary({ error, retry }: ErrorBoundaryProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const segments = useSegments();
  // The route that crashed: segments follow whatever opens over this view later.
  // The chat's are empty; its file is `index`.
  const [screen] = useState(() => segments.join("/") || "index");
  // The screen this view stands in for, in the stack that holds it; at the
  // root, the router's own one-screen slot, which can never go back.
  const navigation = useContext(NavigationContext);
  const canGoBack = !useContext(HeaderShownContext) && (navigation?.canGoBack() ?? false);

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
      {/* After the view, so it is drawn over it and takes the tap. */}
      {canGoBack ? <StackBackButton style={[s.back, { top: insets.top + Space.md }]} /> : null}
    </View>
  );
}

const s = StyleSheet.create({
  page: { flex: 1 },
  back: { position: "absolute", left: Space.md },
});
