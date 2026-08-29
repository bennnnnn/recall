import { useMemo } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Props = {
  title: string;
  onCancel: () => void;
  onSave: () => void;
  cancelLabel: string;
  saveLabel: string;
  saving?: boolean;
  saveDisabled?: boolean;
  cancelDisabled?: boolean;
};

/** Cancel / title / Save row for form AppSheets (rename, settings, reminder, due, memory). */
export function SheetFormHeader({
  title,
  onCancel,
  onSave,
  cancelLabel,
  saveLabel,
  saving = false,
  saveDisabled = false,
  cancelDisabled = false,
}: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const saveBlocked = saving || saveDisabled;
  const cancelBlocked = saving || cancelDisabled;

  return (
    <View style={s.header}>
      <Pressable
        onPress={onCancel}
        hitSlop={8}
        disabled={cancelBlocked}
        accessible
        accessibilityRole="button"
        accessibilityLabel={cancelLabel}
        accessibilityState={{ disabled: cancelBlocked }}
        testID="sheet-form-header-cancel"
        style={s.side}
      >
        <Text style={s.cancelText}>{cancelLabel}</Text>
      </Pressable>
      <Text style={s.title} numberOfLines={1}>
        {title}
      </Text>
      <Pressable
        onPress={onSave}
        hitSlop={8}
        disabled={saveBlocked}
        accessible
        accessibilityRole="button"
        accessibilityLabel={saveLabel}
        accessibilityState={{ disabled: saveBlocked, busy: saving }}
        testID="sheet-form-header-save"
        style={s.side}
      >
        {saving ? (
          <ActivityIndicator size="small" color={theme.primary} />
        ) : (
          <Text style={[s.saveText, saveDisabled && s.saveDisabled]}>{saveLabel}</Text>
        )}
      </Pressable>
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    header: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingHorizontal: Space.md,
      minHeight: Space.minTouch + 8,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: C.border,
      gap: Space.sm,
    },
    side: {
      minWidth: 64,
      minHeight: Space.minTouch,
      justifyContent: "center",
    },
    title: {
      flex: 1,
      ...Type.navTitle,
      color: C.text,
      textAlign: "center",
    },
    cancelText: { ...Type.body, color: C.textSecondary },
    saveText: { ...Type.body, fontWeight: "700", color: C.primary, textAlign: "right" },
    saveDisabled: { opacity: 0.4 },
  });
}
