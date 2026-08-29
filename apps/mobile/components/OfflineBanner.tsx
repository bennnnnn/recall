import { StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { Layer } from "@/lib/layer";
import type { ConnectivityStatus } from "@/lib/networkProbe";
import { Theme, useTheme } from "@/lib/theme";

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
    <View style={[s.wrap, { paddingTop: insets.top + 6 }]} accessibilityRole="alert">
      <Icon name="cloud-offline-outline" size={16} color={theme.onWarning} />
      <Text style={s.text}>{label}</Text>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    wrap: {
      position: "absolute",
      top: 0,
      left: 0,
      right: 0,
      zIndex: Layer.toast,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
      paddingBottom: 8,
      paddingHorizontal: 16,
      backgroundColor: theme.warning,
    },
    text: {
      fontSize: 13,
      fontWeight: "700",
      color: theme.onWarning,
    },
  });
}
