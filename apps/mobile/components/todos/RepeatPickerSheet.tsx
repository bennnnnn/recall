import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import type { RecurrenceRule } from "@/lib/api";
import { selection } from "@/lib/haptics";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { RECURRENCE_RULES } from "@/lib/todos/recurrence";

export const REPEAT_PICKER_VALUES: readonly (RecurrenceRule | null)[] = [
  null,
  ...RECURRENCE_RULES,
];

export function repeatMessageKey(
  rule: RecurrenceRule | null,
): "todos.repeat_none" | `todos.repeat_${RecurrenceRule}` {
  return rule == null ? "todos.repeat_none" : `todos.repeat_${rule}`;
}

/** Pick-one list for reminder repeat. Must live in the parent sheet — a nested AppSheet never presents on iOS. */
export function RepeatPickerSheet({
  selected,
  onSelect,
}: {
  selected: RecurrenceRule | null;
  onSelect: (rule: RecurrenceRule | null) => void;
}) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);

  const pick = (rule: RecurrenceRule | null) => {
    selection();
    onSelect(rule);
  };

  return (
    <View style={s.menu}>
      {REPEAT_PICKER_VALUES.map((rule) => {
        const active = rule === selected;
        const label = t(repeatMessageKey(rule));
        return (
          <Pressable
            key={repeatMessageKey(rule)}
            style={({ pressed }) => [
              s.item,
              active && s.itemActive,
              pressed && s.itemPressed,
            ]}
            onPress={() => pick(rule)}
            accessibilityRole="radio"
            accessibilityState={{ selected: active }}
            accessibilityLabel={label}
          >
            <Text style={[s.label, active && s.labelActive]}>{label}</Text>
            {active ? <Icon name="checkmark" size={18} color={theme.primary} /> : null}
          </Pressable>
        );
      })}
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    menu: {
      borderWidth: 1,
      borderColor: C.border,
      borderTopWidth: 0,
      borderBottomLeftRadius: Radius.md,
      borderBottomRightRadius: Radius.md,
      overflow: "hidden",
      backgroundColor: C.surface,
    },
    item: {
      flexDirection: "row",
      alignItems: "center",
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      gap: Space.sm,
      minHeight: Space.minTouch,
    },
    itemPressed: {
      backgroundColor: C.surfaceAlt,
    },
    itemActive: {
      backgroundColor: C.primaryLight,
    },
    label: {
      fontSize: 17,
      color: C.text,
      fontWeight: "400",
      flex: 1,
    },
    labelActive: {
      fontWeight: "600",
      color: C.primary,
    },
  });
}
