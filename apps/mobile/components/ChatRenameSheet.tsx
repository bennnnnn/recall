import { useMemo } from "react";
import {
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
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
  const insets = useSafeAreaInsets();

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <KeyboardAvoidingView
        style={s.overlay}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <Pressable style={s.backdrop} onPress={onClose} />
        <View style={[s.sheet, { paddingBottom: insets.bottom }]}>
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
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    overlay: {
      flex: 1,
      justifyContent: "flex-end",
    },
    backdrop: {
      ...StyleSheet.absoluteFill,
      backgroundColor: C.scrim,
    },
    sheet: {
      backgroundColor: C.bg,
      borderTopLeftRadius: 20,
      borderTopRightRadius: 20,
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
