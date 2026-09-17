import { useMemo } from "react";
import { Pressable, StyleSheet, TextInput, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";

/** Minimal reply bar for an automation's live chat — text only (no attach,
 * voice, or math keyboard). `ChatComposer` is deliberately not reused here:
 * it reads from the global `ComposerDraftContext` and wires attach/voice/
 * live-talk affordances this screen doesn't support, so reusing it would
 * either need a second draft-context slot or ship dead buttons. */
export function AutomationComposer({
  value,
  onChangeValue,
  onSend,
  onStop,
  streaming,
  disabled = false,
}: {
  value: string;
  onChangeValue: (text: string) => void;
  onSend: () => void;
  onStop: () => void;
  streaming: boolean;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const canSend = !streaming && !disabled && value.trim().length > 0;

  return (
    <View style={s.bar}>
      <TextInput
        style={s.input}
        value={value}
        onChangeText={onChangeValue}
        placeholder={t("chat.placeholder")}
        placeholderTextColor={C.textDisabled}
        multiline
        maxLength={4000}
        editable={!disabled}
      />
      {streaming ? (
        <Pressable
          style={s.sendBtn}
          onPress={onStop}
          hitSlop={6}
          accessibilityRole="button"
          accessibilityLabel={t("chat.stop_a11y")}
        >
          <Icon name="stop" size={14} color={C.onPrimary} />
        </Pressable>
      ) : (
        <Pressable
          style={[s.sendBtn, !canSend && s.sendBtnDisabled]}
          onPress={onSend}
          disabled={!canSend}
          hitSlop={6}
          accessibilityRole="button"
          accessibilityLabel={t("chat.send_a11y")}
        >
          <Icon name="arrow-up" size={18} color={canSend ? C.onPrimary : C.textTertiary} />
        </Pressable>
      )}
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    bar: {
      flexDirection: "row",
      alignItems: "flex-end",
      gap: Space.sm,
      paddingHorizontal: Space.md,
      paddingTop: Space.sm,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: C.border,
      backgroundColor: C.bg,
    },
    input: {
      flex: 1,
      maxHeight: 120,
      minHeight: Space.minTouch,
      backgroundColor: C.surface,
      borderRadius: Radius.lg,
      borderWidth: 1,
      borderColor: C.border,
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      color: C.text,
    },
    sendBtn: {
      width: Space.minTouch,
      height: Space.minTouch,
      borderRadius: Radius.full,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: C.primary,
    },
    sendBtnDisabled: { backgroundColor: C.surfaceAlt },
  });
}
