/**
 * Floating choice popup for Settings (centered card).
 * One sheet per choice row — do not expand options inside the gray card.
 */
import { useMemo } from "react";
import { Pressable, ScrollView, StyleSheet, Text } from "react-native";

import { AppSheet } from "@/components/AppSheet";
import { Icon } from "@/components/Icon";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Option = { key: string; label: string };

type Props = {
  visible: boolean;
  options: Option[];
  selectedKey: string;
  disabled?: boolean;
  /** Optional; some Settings screens pass a sheet title. The card itself is unlabeled. */
  title?: string;
  busy?: boolean;
  onClose: () => void;
  onSelect: (key: string) => void;
};

export function SettingsPickerSheet({
  visible,
  options,
  selectedKey,
  disabled,
  busy,
  onClose,
  onSelect,
}: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const locked = Boolean(disabled || busy);

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
        contentContainerStyle={s.options}
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
              disabled={locked}
              accessibilityRole="radio"
              accessibilityState={{ selected: active, disabled: locked }}
              accessibilityLabel={option.label}
              onPress={() => {
                if (locked) return;
                if (!active) onSelect(option.key);
                onClose();
              }}
            >
              <Text style={s.optionText}>{option.label}</Text>
              {active ? <Icon name="checkmark" size={22} color={theme.primary} /> : null}
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
      borderRadius: 28,
      width: "86%",
      maxWidth: 340,
      padding: 0,
    },
    scroll: {
      maxHeight: 360,
    },
    options: {
      gap: 2,
    },
    option: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: Space.gutter,
      minHeight: 68,
      padding: Space.gutter,
      borderRadius: 4,
      backgroundColor: t.settingsSurface,
    },
    optionPressed: {
      opacity: 0.65,
    },
    optionText: {
      flex: 1,
      ...Type.body,
      fontSize: 18,
      color: t.text,
    },
  });
}
