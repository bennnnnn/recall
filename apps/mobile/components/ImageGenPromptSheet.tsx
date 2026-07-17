import { useEffect, useMemo, useState } from "react";
import { Keyboard, StyleSheet, Text, TextInput, View } from "react-native";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { Button } from "@/components/Button";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  visible: boolean;
  generating: boolean;
  /** Pre-fill the prompt (e.g. detected from typed chat text) — editable before submit. */
  initialPrompt?: string | null;
  onClose: () => void;
  onSubmit: (prompt: string) => void;
};

export function ImageGenPromptSheet({
  visible,
  generating,
  initialPrompt,
  onClose,
  onSubmit,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [prompt, setPrompt] = useState("");

  useEffect(() => {
    if (visible) setPrompt(initialPrompt?.trim() ?? "");
    // Only re-seed when the sheet transitions to visible, not on every
    // initialPrompt change while it's open — the user may be editing it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);

  const handleClose = () => {
    if (generating) return;
    setPrompt("");
    onClose();
  };

  const handleSubmit = () => {
    const trimmed = prompt.trim();
    if (!trimmed || generating) return;
    Keyboard.dismiss();
    onSubmit(trimmed);
  };

  return (
    <AppSheet
      visible={visible}
      onClose={handleClose}
      variant="bottom"
      animation="fade"
      keyboardAvoiding
      withHandle={false}
      minBottomPadding={16}
      contentContainerStyle={s.sheet}
    >
      <Text style={s.title}>{t("chat.image_gen_title")}</Text>
      <TextInput
        style={s.input}
        value={prompt}
        onChangeText={setPrompt}
        placeholder={t("chat.image_gen_placeholder")}
        placeholderTextColor={theme.textTertiary}
        multiline
        maxLength={2000}
        editable={!generating}
        autoFocus
      />
      <View style={s.actions}>
        <Button
          title={t("common.cancel")}
          onPress={handleClose}
          variant="ghost"
          disabled={generating}
        />
        <Button
          title={t("chat.image_gen_generate")}
          onPress={handleSubmit}
          loading={generating}
          disabled={!prompt.trim()}
          style={s.primaryBtn}
        />
      </View>
    </AppSheet>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    sheet: {
      backgroundColor: t.surface,
      borderTopLeftRadius: 24,
      borderTopRightRadius: 24,
      paddingHorizontal: 20,
      paddingTop: 20,
      gap: 12,
    },
    title: {
      fontSize: 18,
      fontWeight: "600",
      color: t.text,
    },
    input: {
      minHeight: 96,
      maxHeight: 160,
      borderRadius: 14,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      paddingHorizontal: 14,
      paddingVertical: 12,
      fontSize: 16,
      lineHeight: 22,
      color: t.text,
      textAlignVertical: "top",
    },
    actions: {
      flexDirection: "row",
      justifyContent: "flex-end",
      alignItems: "center",
      gap: 10,
      marginTop: 4,
    },
    primaryBtn: {
      minWidth: 120,
    },
  });
}
