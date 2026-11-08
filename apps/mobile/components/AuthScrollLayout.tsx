import { type ReactNode } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Space } from "@/lib/space";

/** Cap auth columns on tablet so login/onboarding don't stretch edge-to-edge. */
export const AUTH_COLUMN_MAX_WIDTH = 420;

type Props = {
  children: ReactNode;
  /** How to distribute hero vs actions when the column is taller than content. */
  justify?: "space-between" | "center";
  /**
   * The screen's actions, pinned under the scroll and above the system bars. A phone with
   * display zoom up (a Galaxy S23 at 339 × 727 dp, 2026-11-07) scrolled "Get started" under
   * Android's navigation buttons; a pinned footer is on screen at every size.
   */
  footer?: ReactNode;
};

/**
 * Scroll + keyboard-safe column for login and onboarding. `flexGrow: 1` keeps
 * short content filling the screen; small/landscape devices can still scroll.
 */
export function AuthScrollLayout({
  children,
  justify = "space-between",
  footer,
}: Props) {
  const insets = useSafeAreaInsets();
  const bottom = Math.max(insets.bottom, Space.md);

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        contentContainerStyle={[
          styles.scroll,
          {
            paddingTop: Math.max(insets.top, Space.md),
            paddingBottom: footer ? Space.md : bottom,
          },
        ]}
        testID="auth-scroll-layout"
      >
        <View style={[styles.column, { justifyContent: justify }]}>{children}</View>
      </ScrollView>
      {footer ? (
        <View style={[styles.footer, { paddingBottom: bottom }]} testID="auth-scroll-footer">
          <View style={styles.footerColumn}>{footer}</View>
        </View>
      ) : null}
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  scroll: {
    flexGrow: 1,
    paddingHorizontal: Space.lg,
  },
  column: {
    flexGrow: 1,
    width: "100%",
    maxWidth: AUTH_COLUMN_MAX_WIDTH,
    alignSelf: "center",
  },
  footer: {
    paddingTop: Space.sm,
    paddingHorizontal: Space.lg,
  },
  footerColumn: {
    width: "100%",
    maxWidth: AUTH_COLUMN_MAX_WIDTH,
    alignSelf: "center",
  },
});
