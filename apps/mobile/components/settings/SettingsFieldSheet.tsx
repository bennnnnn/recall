/**
 * Bottom-sheet text editor for settings (profile fields, custom instructions).
 * Matches ChatRenameSheet AppSheet pattern.
 */
import { useMemo } from "react";
import {
  ActivityIndicator,
  InputAccessoryView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
  type KeyboardTypeOptions,
} from "react-native";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

const EMPTY_NUMBER_PAD_ACCESSORY_ID = "settings-field-empty-accessory";

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
  saving?: boolean;
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
  saving = false,
}: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const numberPad =
    keyboardType === "number-pad" || keyboardType === "decimal-pad";
  // iOS number-pad has no Return key, so RN mounts a floating Done accessory
  // that duplicates this sheet's Save. An empty accessory replaces it.
  const hideNumberPadDone = Platform.OS === "ios" && numberPad;

  return (
    <>
      {hideNumberPadDone && visible ? (
        <InputAccessoryView nativeID={EMPTY_NUMBER_PAD_ACCESSORY_ID}>
          <View />
        </InputAccessoryView>
      ) : null}
    <AppSheet
      visible={visible}
      onClose={() => {
        if (!saving) onClose();
      }}
      variant="bottom"
      keyboardAvoiding
      withHandle={false}
      contentContainerStyle={s.sheet}
    >
      <View style={s.header}>
        <Pressable
          onPress={onClose}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel={t("settings.cancel")}
          disabled={saving}
        >
          <Text style={s.cancelText}>{t("settings.cancel")}</Text>
        </Pressable>
        <Text style={s.title} numberOfLines={1}>
          {title}
        </Text>
        <Pressable
          onPress={onSave}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel={t("settings.save")}
          disabled={saving}
          accessibilityState={{ disabled: saving, busy: saving }}
        >
          {saving ? (
            <ActivityIndicator size="small" color={theme.primary} />
          ) : (
            <Text style={s.saveText}>{t("settings.save")}</Text>
          )}
        </Pressable>
      </View>
      <View style={s.body}>
        {hint ? <Text style={s.hint}>{hint}</Text> : null}
        <TextInput
          style={[s.input, multiline && s.inputMultiline]}
          value={value}
          onChangeText={onChangeText}
          autoFocus
          returnKeyType={multiline || numberPad ? "default" : "done"}
          onSubmitEditing={multiline || numberPad ? undefined : onSave}
          inputAccessoryViewID={
            hideNumberPadDone ? EMPTY_NUMBER_PAD_ACCESSORY_ID : undefined
          }
          maxLength={maxLength}
          placeholder={placeholder}
          placeholderTextColor={theme.textDisabled}
          keyboardType={keyboardType}
          multiline={multiline}
          textAlignVertical={multiline ? "top" : "center"}
          editable={!saving}
        />
      </View>
    </AppSheet>
    </>
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
      paddingHorizontal: Space.md,
      paddingVertical: 14,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: C.border,
      gap: Space.sm,
    },
    title: { flex: 1, ...Type.navTitle, color: C.text, textAlign: "center" },
    cancelText: { ...Type.body, color: C.textSecondary, minWidth: 64 },
    saveText: { ...Type.body, fontWeight: "700", color: C.primary, minWidth: 64, textAlign: "right" },
    body: { padding: Space.md, gap: 10 },
    hint: { ...Type.caption, fontWeight: "400", color: C.textSecondary, lineHeight: 18 },
    input: {
      backgroundColor: C.contentSurface,
      borderRadius: 12,
      paddingHorizontal: 14,
      paddingVertical: Space.sm,
      ...Type.body,
      color: C.text,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
    },
    inputMultiline: {
      minHeight: 120,
    },
  });
}
