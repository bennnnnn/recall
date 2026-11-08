import { Platform, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { todoViewCopy } from "@/features/todos/components/todoViews";
import type { TodoView } from "@/features/todos/model/todoListFilter";
import { useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

/**
 * Two lines (22 + 16pt) fill most of the 44pt bar at the default size, and the native title
 * does not grow with Dynamic Type either: at iOS XX-Large they stood 47pt, taller than the bar.
 */
const HEADER_TITLE_MAX_SCALE = 1;

/**
 * The To-do header's title, with the list's view on a line under it ("Today", "Completed").
 * The view was named only inside the ⋯ menu, so a list gave no sign of which one it showed.
 * Null `view` (a to-do's own page) draws the title alone.
 */
export function TodosHeaderTitle({ view }: { view: TodoView | null }) {
  const { t } = useTranslation();
  const C = useTheme();
  const title = t("drawer.reminders");
  const viewLabel = view ? t(todoViewCopy(view).label) : null;

  return (
    <View
      style={styles.wrap}
      accessible
      accessibilityRole="header"
      accessibilityLabel={viewLabel ? `${title}, ${viewLabel}` : title}
    >
      <Text
        style={[Type.navTitle, { color: C.text }]}
        numberOfLines={1}
        maxFontSizeMultiplier={HEADER_TITLE_MAX_SCALE}
      >
        {title}
      </Text>
      {viewLabel ? (
        <Text
          style={[Type.caption, { color: C.textSecondary }]}
          numberOfLines={1}
          maxFontSizeMultiplier={HEADER_TITLE_MAX_SCALE}
        >
          {viewLabel}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  // iOS centres the title in the bar; Android starts it after the back button.
  wrap: { alignItems: Platform.OS === "ios" ? "center" : "flex-start" },
});
