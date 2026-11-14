import { Platform, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

/** The native title does not grow with Dynamic Type either: past it, the title stood taller than the 44pt bar. */
const HEADER_TITLE_MAX_SCALE = 1;

/**
 * The To-do header's title. Drawn here, not as the native title, so the new to-do sheet
 * can hide it from a screen reader with the rest of the page (useTodosHeader).
 */
export function TodosHeaderTitle() {
  const { t } = useTranslation();
  const C = useTheme();
  const title = t("drawer.reminders");

  return (
    <View style={styles.wrap} accessible accessibilityRole="header" accessibilityLabel={title}>
      <Text
        style={[Type.navTitle, { color: C.text }]}
        numberOfLines={1}
        maxFontSizeMultiplier={HEADER_TITLE_MAX_SCALE}
      >
        {title}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  // iOS centres the title in the bar; Android starts it after the back button.
  wrap: { alignItems: Platform.OS === "ios" ? "center" : "flex-start" },
});
