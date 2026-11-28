import type { ReactNode } from "react";
import { StyleSheet, Text, View } from "react-native";
import { SafeAreaProvider, useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Icon } from "@/ui/icons/Icon";
import type { ConnectivityStatus } from "@/lib/networkProbe";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Space } from "@/lib/space";
import { IconSize } from "@/ui/icons/sizes";
import { WindowInsetsProvider } from "@/ui/hooks/useWindowInsets";

type Props = {
  status: ConnectivityStatus;
};

export function OfflineBanner({ status }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const s = makeStyles(theme);

  if (status === "online") return null;

  const label =
    status === "api_unreachable" ? t("common.api_unreachable") : t("common.no_internet");

  return (
    <View
      style={[s.wrap, { paddingTop: insets.top + 6 }]}
      accessibilityRole="alert"
      testID="offline-banner"
    >
      <Icon name="cloud-off" size={IconSize.xs} color={theme.onWarning} />
      <Text style={s.text}>{label}</Text>
    </View>
  );
}

/**
 * The app under the offline banner. The banner lay over the screen and covered its header
 * (the menu, New chat, Back); it now takes its own room at the top and the screens sit
 * below it. The screens read their safe area from their own provider, so under the banner,
 * which already covers the status bar, a header adds no second status-bar gap. The provider
 * is there online too, so the banner coming and going never remounts the screens.
 */
export function OfflineFrame({ status, children }: Props & { children: ReactNode }) {
  return (
    // A sheet, menu or full-screen page drawn over the window reads the window's insets.
    <WindowInsetsProvider>
      <View style={styles.frame}>
        <OfflineBanner status={status} />
        <SafeAreaProvider style={styles.frame} testID="offline-frame-screens">
          {children}
        </SafeAreaProvider>
      </View>
    </WindowInsetsProvider>
  );
}

const styles = StyleSheet.create({ frame: { flex: 1 } });

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    wrap: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: Space.xs,
      paddingBottom: Space.xs,
      paddingHorizontal: Space.md,
      backgroundColor: theme.warning,
    },
    text: {
      ...Type.compact,
      ...Weight.bold,
      color: theme.onWarning,
      flexShrink: 1,
      textAlign: "center",
    },
  });
}
