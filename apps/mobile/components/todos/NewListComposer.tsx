import { useEffect, useMemo, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

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
        <Button
          title={t("common.add")}
          onPress={submit}
          disabled={!canSave}
          style={s.addButton}
        />
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
      paddingBottom: Space.xxs,
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingHorizontal: Space.md,
      paddingTop: Space.sm,
      paddingBottom: Space.xxs,
    },
    title: {
      ...Type.secondary,
      fontWeight: "700",
      color: C.text,
    },
    cancel: {
      ...Type.secondary,
      color: C.textSecondary,
    },
    row: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
    },
    inputWrap: {
      flex: 1,
      borderWidth: hairline,
      borderColor: C.border,
      borderRadius: Radius.sm,
      paddingHorizontal: Space.sm,
      paddingVertical: Space.xs,
      backgroundColor: C.bg,
    },
    input: {
      ...Type.body,
      lineHeight: 22,
      color: C.text,
      paddingVertical: 0,
    },
    addButton: {
      minHeight: 40,
      paddingHorizontal: Space.md,
      paddingVertical: Space.xs,
    },
  });
}
