import { useMemo } from "react";
import { Platform, Pressable, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { FullWindowOverlay } from "react-native-screens";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { makeTodosStyles } from "@/features/todos/components/todosStyles";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

/** Height of the stack header under the status bar. */
const HEADER_BODY = 44;

/** Dropdown under the detail header. The page stays put underneath. */
export function TodoDetailMenu({
  checked,
  onMarkDone,
  onDelete,
  onClose,
}: {
  checked: boolean;
  onMarkDone: () => void;
  onDelete: () => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const s = useMemo(() => makeTodosStyles(theme), [theme]);
  const doneLabel = checked ? t("todos.mark_open") : t("todos.selection_complete");
  const top = Platform.OS === "ios" ? insets.top + HEADER_BODY + Space.xxs : Space.xs;

  const menu = (
    <View style={s.menuLayer} pointerEvents="box-none">
      <Pressable
        style={s.menuScrim}
        onPress={onClose}
        accessibilityRole="button"
        accessibilityLabel={t("common.close")}
      />
      <View style={[s.menuCard, { top }]}>
        <Pressable
          style={({ pressed }) => [s.menuItem, pressed && s.menuItemPressed]}
          onPress={onMarkDone}
          accessibilityRole="button"
          accessibilityLabel={doneLabel}
        >
          <Text style={s.menuLabel}>{doneLabel}</Text>
        </Pressable>
        <Pressable
          style={({ pressed }) => [s.menuItem, pressed && s.menuItemPressed]}
          onPress={onDelete}
          accessibilityRole="button"
          accessibilityLabel={t("common.delete")}
        >
          <Text style={[s.menuLabel, { color: theme.danger }]}>{t("common.delete")}</Text>
        </Pressable>
      </View>
    </View>
  );

  // The list sits in a native scroll view under the stack header. An in-screen
  // overlay paints behind both, so the menu never shows. On iOS this window
  // is above the header; Android keeps the elevated layer in the screen.
  if (Platform.OS === "ios") return <FullWindowOverlay>{menu}</FullWindowOverlay>;
  return <View style={s.menuLayer}>{menu}</View>;
}
