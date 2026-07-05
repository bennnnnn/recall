import { useEffect, useMemo, useState } from "react";
import { Modal, Pressable, Text, TextInput, View } from "react-native";
import { useTranslation } from "react-i18next";

import { useTheme } from "@/lib/theme";
import { makeTodosStyles } from "@/components/todos/todosStyles";

export function NewListSheet({
  visible,
  onClose,
  onSave,
}: {
  visible: boolean;
  onClose: () => void;
  onSave: (name: string) => void;
}) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const [name, setName] = useState("");

  useEffect(() => {
    if (!visible) setName("");
  }, [visible]);

  const canSave = name.trim().length > 0;

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={s.sheetOverlay}>
        <Pressable style={s.sheetBackdrop} onPress={onClose} />
        <View style={s.sheet}>
          <View style={s.sheetHeader}>
            <Pressable onPress={onClose} hitSlop={8}>
              <Text style={s.sheetCancel}>{t("common.cancel")}</Text>
            </Pressable>
            <Text style={s.sheetTitle}>{t("lists.new_group_title")}</Text>
            <Pressable
              onPress={() => canSave && onSave(name.trim())}
              hitSlop={8}
              disabled={!canSave}
            >
              <Text style={[s.sheetSave, !canSave && s.sheetSaveDisabled]}>
                {t("todos.save")}
              </Text>
            </Pressable>
          </View>
          <View style={s.sheetBody}>
            <Text style={s.formLabel}>{t("lists.group_name_label")}</Text>
            <TextInput
              style={s.titleInput}
              placeholder={t("lists.group_name_placeholder")}
              placeholderTextColor={C.textTertiary}
              value={name}
              onChangeText={setName}
              autoFocus
              returnKeyType="done"
              maxLength={200}
            />
          </View>
        </View>
      </View>
    </Modal>
  );
}
