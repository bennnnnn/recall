import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Theme, useTheme } from "@/lib/theme";

type Props = {
  visible: boolean;
};

export function OfflineBanner({ visible }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const s = makeStyles(theme);

  if (!visible) return null;

  return (
    <View style={[s.wrap, { paddingTop: insets.top + 6 }]} accessibilityRole="alert">
      <Ionicons name="cloud-offline-outline" size={16} color={theme.text} />
      <Text style={s.text}>{t("common.no_internet")}</Text>
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
      zIndex: 9999,
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
      color: theme.text,
    },
  });
}
