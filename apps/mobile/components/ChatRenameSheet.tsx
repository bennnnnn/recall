import { useMemo } from "react";
import {
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useTranslation } from "react-i18next";

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
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={s.overlay} onPress={onClose}>
        <Pressable style={s.sheet} onPress={(e) => e.stopPropagation()}>
          <Text style={s.title}>{t("chat.rename_title")}</Text>
          <TextInput
            style={s.input}
            value={value}
            onChangeText={onChangeText}
            autoFocus
            returnKeyType="done"
            onSubmitEditing={onSave}
            maxLength={80}
          />
          <View style={s.row}>
            <Pressable style={s.cancel} onPress={onClose}>
              <Text style={s.cancelText}>{t("common.cancel")}</Text>
            </Pressable>
            <Pressable style={s.save} onPress={onSave}>
              <Text style={s.saveText}>{t("settings.save")}</Text>
            </Pressable>
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    overlay: {
      flex: 1,
      backgroundColor: "rgba(0,0,0,0.4)",
      justifyContent: "center",
      padding: 24,
    },
    sheet: { backgroundColor: C.bg, borderRadius: 20, padding: 20, gap: 14 },
    title: { fontSize: 17, fontWeight: "700", color: C.text },
    input: {
      backgroundColor: C.surface,
      borderRadius: 12,
      padding: 12,
      fontSize: 16,
      color: C.text,
      borderWidth: 1.5,
      borderColor: C.primary,
    },
    row: { flexDirection: "row", gap: 10 },
    cancel: {
      flex: 1,
      borderRadius: 12,
      borderWidth: 1,
      borderColor: C.border,
      padding: 12,
      alignItems: "center",
    },
    cancelText: { fontSize: 15, color: C.textSecondary, fontWeight: "600" },
    save: {
      flex: 1,
      borderRadius: 12,
      backgroundColor: C.primary,
      padding: 12,
      alignItems: "center",
    },
    saveText: { fontSize: 15, color: "#fff", fontWeight: "700" },
  });
}
