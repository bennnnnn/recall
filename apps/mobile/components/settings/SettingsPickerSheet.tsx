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

type Option = { key: string; label: string; disabled?: boolean; note?: string };

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
          const optionDisabled = locked || Boolean(option.disabled);
          return (
            <Pressable
              key={option.key}
              style={({ pressed }) => [
                s.option,
                pressed && !optionDisabled && s.optionPressed,
              ]}
              disabled={optionDisabled}
              accessibilityRole="radio"
              accessibilityState={{ selected: active, disabled: optionDisabled }}
              accessibilityLabel={option.label}
              onPress={() => {
                if (optionDisabled) return;
                if (!active) onSelect(option.key);
                onClose();
              }}
            >
              <Text style={[s.optionText, optionDisabled && s.optionTextDisabled]}>
                {option.label}
              </Text>
              {active ? (
                <Icon name="checkmark" size={22} color={theme.primary} />
              ) : option.note ? (
                <Text style={s.optionNote}>{option.note}</Text>
              ) : null}
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
      borderRadius: Radius.sheet,
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
      gap: Space.md,
      minHeight: 56,
      padding: Space.md,
      borderRadius: 4,
      backgroundColor: t.settingsSurface,
    },
    optionPressed: {
      opacity: 0.65,
    },
    optionText: {
      flex: 1,
      ...Type.body,
      color: t.text,
    },
    optionTextDisabled: {
      color: t.textTertiary,
    },
    optionNote: {
      ...Type.caption,
      color: t.primary,
      fontWeight: "600",
    },
  });
}
