/**
 * Bottom-sheet text editor for settings (profile fields, custom instructions).
 * Matches ChatRenameSheet / SettingsPickerModal AppSheet pattern.
 */
import { useMemo } from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
  type KeyboardTypeOptions,
} from "react-native";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  visible: boolean;
  title: string;
  value: string;
  onChangeText: (text: string) => void;
  onClose: () => void;
  onSave: () => void;
  hint?: string;
  placeholder?: string;
  maxLength?: number;
  multiline?: boolean;
  keyboardType?: KeyboardTypeOptions;
};

export function SettingsFieldSheet({
  visible,
  title,
  value,
  onChangeText,
  onClose,
  onSave,
  hint,
  placeholder,
  maxLength,
  multiline = false,
  keyboardType = "default",
}: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <AppSheet
      visible={visible}
      onClose={onClose}
      variant="bottom"
      keyboardAvoiding
      withHandle={false}
      contentContainerStyle={s.sheet}
    >
      <View style={s.header}>
        <Pressable onPress={onClose} hitSlop={8} accessibilityRole="button">
          <Text style={s.cancelText}>{t("settings.cancel")}</Text>
        </Pressable>
        <Text style={s.title} numberOfLines={1}>
          {title}
        </Text>
        <Pressable onPress={onSave} hitSlop={8} accessibilityRole="button">
          <Text style={s.saveText}>{t("settings.save")}</Text>
        </Pressable>
      </View>
      <View style={s.body}>
        {hint ? <Text style={s.hint}>{hint}</Text> : null}
        <TextInput
          style={[s.input, multiline && s.inputMultiline]}
          value={value}
          onChangeText={onChangeText}
          autoFocus
          returnKeyType={multiline ? "default" : "done"}
          onSubmitEditing={multiline ? undefined : onSave}
          maxLength={maxLength}
          placeholder={placeholder}
          placeholderTextColor={theme.textTertiary}
          keyboardType={keyboardType}
          multiline={multiline}
          textAlignVertical={multiline ? "top" : "center"}
        />
      </View>
    </AppSheet>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    sheet: {
      paddingHorizontal: 0,
      paddingTop: 0,
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingHorizontal: 16,
      paddingVertical: 14,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: C.border,
      gap: 12,
    },
    title: { flex: 1, fontSize: 17, fontWeight: "700", color: C.text, textAlign: "center" },
    cancelText: { fontSize: 16, color: C.textSecondary, minWidth: 64 },
    saveText: { fontSize: 16, fontWeight: "700", color: C.primary, minWidth: 64, textAlign: "right" },
    body: { padding: 16, gap: 10 },
    hint: { fontSize: 13, color: C.textSecondary, lineHeight: 18 },
    input: {
      backgroundColor: C.contentSurface,
      borderRadius: 12,
      paddingHorizontal: 14,
      paddingVertical: 12,
      fontSize: 16,
      color: C.text,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
    },
    inputMultiline: {
      minHeight: 120,
    },
  });
}
