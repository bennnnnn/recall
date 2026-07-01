import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

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
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.pickerBackdrop}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} />
        <View style={styles.pickerSheet}>
          <Text style={styles.pickerTitle}>{title}</Text>
          {options.map((option) => {
            const active = selectedKey === option.key;
            return (
              <Pressable
                key={option.key}
                style={[styles.pickerOption, active && styles.pickerOptionActive]}
                disabled={disabled}
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
        </View>
      </View>
    </Modal>
  );
}
