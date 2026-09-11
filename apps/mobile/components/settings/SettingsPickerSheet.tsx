/**
 * Floating choice popup for Settings (centered card).
 * One sheet per choice row — do not expand options inside the gray card.
 */
import { useMemo } from "react";
import { Pressable, ScrollView, StyleSheet, Text } from "react-native";

import { AppSheet } from "@/components/AppSheet";
import { Icon } from "@/components/Icon";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Option = { key: string; label: string };

type Props = {
  visible: boolean;
  options: Option[];
  selectedKey: string;
  disabled?: boolean;
  onClose: () => void;
  onSelect: (key: string) => void;
};

export function SettingsPickerSheet({
  visible,
  options,
  selectedKey,
  disabled,
  onClose,
  onSelect,
}: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <AppSheet
      visible={visible}
      onClose={onClose}
      variant="center"
      withHandle={false}
      contentContainerStyle={s.sheet}
    >
      <ScrollView
        style={s.scroll}
        bounces={false}
        showsVerticalScrollIndicator={false}
        testID="settings-picker-sheet"
      >
        {options.map((option) => {
          const active = option.key === selectedKey;
          return (
            <Pressable
              key={option.key}
              style={({ pressed }) => [s.option, pressed && s.optionPressed]}
              disabled={disabled}
              accessibilityRole="radio"
              accessibilityState={{ selected: active, disabled: Boolean(disabled) }}
              accessibilityLabel={option.label}
              onPress={() => {
                if (!active) onSelect(option.key);
                onClose();
              }}
            >
              <Text style={s.optionText}>{option.label}</Text>
              {active ? <Icon name="checkmark" size={18} color={theme.text} /> : null}
            </Pressable>
          );
        })}
      </ScrollView>
    </AppSheet>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    sheet: {
      backgroundColor: t.bg,
      borderRadius: Radius.xl,
      width: "86%",
      maxWidth: 340,
      paddingVertical: Space.xs,
      paddingHorizontal: Space.xxs,
    },
    scroll: {
      maxHeight: 360,
    },
    option: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: Space.sm,
      minHeight: Space.minTouch,
      paddingHorizontal: Space.md,
      paddingVertical: 12,
    },
    optionPressed: {
      opacity: 0.55,
    },
    optionText: {
      flex: 1,
      ...Type.body,
      fontWeight: "400",
      color: t.text,
    },
  });
}
