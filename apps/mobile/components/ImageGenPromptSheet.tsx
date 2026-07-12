import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Keyboard,
  Modal,
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
  const insets = useSafeAreaInsets();
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
    <Modal visible={visible} transparent animationType="fade" onRequestClose={handleClose}>
      <Pressable style={s.backdrop} onPress={handleClose}>
        <Pressable
          style={[s.sheet, { paddingBottom: Math.max(insets.bottom, 16) }]}
          onPress={(event) => event.stopPropagation()}
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
            <Pressable
              style={({ pressed }) => [s.secondaryBtn, pressed && s.btnPressed]}
              onPress={handleClose}
              disabled={generating}
            >
              <Text style={s.secondaryLabel}>{t("common.cancel")}</Text>
            </Pressable>
            <Pressable
              style={({ pressed }) => [
                s.primaryBtn,
                (!prompt.trim() || generating) && s.primaryBtnDisabled,
                pressed && prompt.trim() && !generating && s.btnPressed,
              ]}
              onPress={handleSubmit}
              disabled={!prompt.trim() || generating}
            >
              {generating ? (
                <ActivityIndicator color={theme.onPrimary} size="small" />
              ) : (
                <Text style={s.primaryLabel}>{t("chat.image_gen_generate")}</Text>
              )}
            </Pressable>
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    backdrop: {
      flex: 1,
      backgroundColor: "rgba(0,0,0,0.45)",
      justifyContent: "flex-end",
    },
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
      gap: 10,
      marginTop: 4,
    },
    secondaryBtn: {
      paddingHorizontal: 16,
      paddingVertical: 12,
      borderRadius: 12,
    },
    secondaryLabel: {
      fontSize: 16,
      color: t.textSecondary,
    },
    primaryBtn: {
      minWidth: 120,
      alignItems: "center",
      paddingHorizontal: 18,
      paddingVertical: 12,
      borderRadius: 12,
      backgroundColor: t.primary,
    },
    primaryBtnDisabled: {
      opacity: 0.5,
    },
    primaryLabel: {
      fontSize: 16,
      fontWeight: "600",
      color: t.onPrimary,
    },
    btnPressed: {
      opacity: 0.85,
    },
  });
}
