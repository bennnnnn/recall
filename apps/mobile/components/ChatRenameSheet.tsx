import { useMemo } from "react";
import { StyleSheet, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Sheet } from "@/ui/overlay/Sheet";
import { SheetFormHeader } from "@/ui/overlay/SheetFormHeader";
import { TextField } from "@/ui/controls/TextField";
import { Theme, useTheme } from "@/lib/theme";
import { Space } from "@/lib/space";

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
    <Sheet
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
        <TextField
          value={value}
          onChangeText={onChangeText}
          autoFocus
          returnKeyType="done"
          onSubmitEditing={onSave}
          maxLength={80}
        />
      </View>
    </Sheet>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    sheet: {
      paddingHorizontal: 0,
      paddingTop: 0,
    },
    body: { padding: Space.md },
  });
}
