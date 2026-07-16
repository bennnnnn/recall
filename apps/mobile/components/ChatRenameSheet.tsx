import { useMemo } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  visible: boolean;
  value: string;
  onChangeText: (text: string) => void;
  onClose: () => void;
  onSave: () => void;
};

export function ChatRenameSheet({
  visible,
  value,
  onChangeText,
  onClose,
  onSave,
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
        <Pressable onPress={onClose} hitSlop={8}>
          <Text style={s.cancelText}>{t("common.cancel")}</Text>
        </Pressable>
        <Text style={s.title}>{t("chat.rename_title")}</Text>
        <Pressable onPress={onSave} hitSlop={8}>
          <Text style={s.saveText}>{t("settings.save")}</Text>
        </Pressable>
      </View>
      <View style={s.body}>
        <TextInput
          style={s.input}
          value={value}
          onChangeText={onChangeText}
          autoFocus
          returnKeyType="done"
          onSubmitEditing={onSave}
          maxLength={80}
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
    },
    title: { fontSize: 17, fontWeight: "700", color: C.text },
    cancelText: { fontSize: 16, color: C.textSecondary },
    saveText: { fontSize: 16, fontWeight: "700", color: C.primary },
    body: { padding: 16 },
    input: {
      backgroundColor: C.surface,
      borderRadius: 12,
      padding: 12,
      fontSize: 16,
      color: C.text,
      borderWidth: 1.5,
      borderColor: C.primary,
    },
  });
}
