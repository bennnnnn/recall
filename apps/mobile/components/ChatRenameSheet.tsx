import { useMemo } from "react";
import { StyleSheet, TextInput, View } from "react-native";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { SheetFormHeader } from "@/components/SheetFormHeader";
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
      <SheetFormHeader
        title={t("chat.rename_title")}
        onCancel={onClose}
        onSave={onSave}
        cancelLabel={t("common.cancel")}
        saveLabel={t("settings.save")}
      />
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
