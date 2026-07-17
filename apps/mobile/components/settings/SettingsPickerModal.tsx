import { Pressable, Text } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { AppSheet } from "@/components/AppSheet";
import { SettingsStyles } from "@/components/settings/settingsUi";
import { Theme } from "@/lib/theme";

type Option = { key: string; label: string };

type Props = {
  visible: boolean;
  title: string;
  options: Option[];
  selectedKey: string;
  onClose: () => void;
  onSelect: (key: string) => void;
  disabled?: boolean;
  styles: SettingsStyles;
  theme: Theme;
};

export function SettingsPickerModal({
  visible,
  title,
  options,
  selectedKey,
  onClose,
  onSelect,
  disabled,
  styles,
  theme,
}: Props) {
  return (
    <AppSheet
      visible={visible}
      onClose={onClose}
      variant="bottom"
      animation="fade"
      withHandle={false}
      minBottomPadding={32}
      contentContainerStyle={styles.pickerSheet}
    >
      <Text style={styles.pickerTitle}>{title}</Text>
      {options.map((option) => {
        const active = selectedKey === option.key;
        return (
          <Pressable
            key={option.key}
            style={[styles.pickerOption, active && styles.pickerOptionActive]}
            disabled={disabled}
            accessibilityRole="radio"
            accessibilityState={{ selected: active }}
            accessibilityLabel={option.label}
            onPress={() => {
              onClose();
              if (!active) onSelect(option.key);
            }}
          >
            <Text style={[styles.pickerOptionText, active && styles.pickerOptionTextActive]}>
              {option.label}
            </Text>
            {active ? <Ionicons name="checkmark" size={18} color={theme.primary} /> : null}
          </Pressable>
        );
      })}
    </AppSheet>
  );
}
