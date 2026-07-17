import { useEffect, useMemo, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Theme, useTheme } from "@/lib/theme";

type Props = {
  onCancel: () => void;
  onSave: (name: string) => void;
};

/**
 * Inline “new list” row on the Lists page — not a Modal sheet, so the OS
 * keyboard resize keeps it on-screen with the rest of the page.
 */
export function NewListComposer({ onCancel, onSave }: Props) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const [name, setName] = useState("");
  const inputRef = useRef<TextInput>(null);
  const canSave = name.trim().length > 0;

  useEffect(() => {
    const id = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(id);
  }, []);

  const submit = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    onSave(trimmed);
  };

  return (
    <View style={s.wrap} accessibilityLabel={t("lists.new_group_title")}>
      <View style={s.header}>
        <Text style={s.title}>{t("lists.new_group_title")}</Text>
        <Pressable onPress={onCancel} hitSlop={8} accessibilityRole="button">
          <Text style={s.cancel}>{t("common.cancel")}</Text>
        </Pressable>
      </View>
      <View style={s.row}>
        <View style={s.inputWrap}>
          <TextInput
            ref={inputRef}
            style={s.input}
            placeholder={t("lists.group_name_placeholder")}
            placeholderTextColor={C.textTertiary}
            value={name}
            onChangeText={setName}
            onSubmitEditing={submit}
            returnKeyType="done"
            maxLength={200}
            autoCorrect={false}
            accessibilityLabel={t("lists.group_name_label")}
          />
        </View>
        <Pressable
          style={[s.addButton, !canSave && s.addButtonDisabled]}
          onPress={submit}
          disabled={!canSave}
          accessibilityRole="button"
          accessibilityState={{ disabled: !canSave }}
          accessibilityLabel={t("common.add")}
        >
          <Text style={s.addButtonText}>{t("common.add")}</Text>
        </Pressable>
      </View>
    </View>
  );
}

function makeStyles(C: Theme) {
  const hairline = StyleSheet.hairlineWidth;
  return StyleSheet.create({
    wrap: {
      borderBottomWidth: hairline,
      borderBottomColor: C.border,
      backgroundColor: C.bg,
      paddingBottom: 4,
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingHorizontal: 16,
      paddingTop: 12,
      paddingBottom: 4,
    },
    title: {
      fontSize: 15,
      fontWeight: "700",
      color: C.text,
    },
    cancel: {
      fontSize: 15,
      color: C.textSecondary,
    },
    row: {
      flexDirection: "row",
      alignItems: "center",
      gap: 8,
      paddingHorizontal: 16,
      paddingVertical: 10,
    },
    inputWrap: {
      flex: 1,
      borderWidth: hairline,
      borderColor: C.border,
      borderRadius: 10,
      paddingHorizontal: 12,
      paddingVertical: 8,
      backgroundColor: C.bg,
    },
    input: {
      fontSize: 16,
      lineHeight: 22,
      color: C.text,
      paddingVertical: 0,
    },
    addButton: {
      paddingHorizontal: 16,
      paddingVertical: 10,
      borderRadius: 10,
      backgroundColor: C.primary,
    },
    addButtonDisabled: {
      opacity: 0.4,
    },
    addButtonText: {
      fontSize: 15,
      fontWeight: "700",
      color: C.onPrimary,
    },
  });
}
