import { Pressable, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import type { ChatScreenStyles } from "@/components/chat/chatScreenStyles";
import type { Theme } from "@/lib/theme";

type Props = {
  styles: ChatScreenStyles;
  theme: Theme;
  bottomOffset: number;
  usedPct: number;
  onUpgrade: () => void;
  onDismiss: () => void;
};

export function ChatQuotaNudge({
  styles: s,
  theme,
  bottomOffset,
  usedPct,
  onUpgrade,
  onDismiss,
}: Props) {
  const { t } = useTranslation();

  return (
    <View style={[s.quotaNudge, { bottom: bottomOffset }]}>
      <Pressable style={s.quotaNudgeBody} onPress={onUpgrade}>
        <Ionicons
          name="flash-outline"
          size={16}
          color={theme.primary}
          style={s.quotaNudgeIcon}
        />
        <Text style={s.quotaNudgeText}>
          {t("chat.quota_nudge_body", { pct: usedPct })}
        </Text>
      </Pressable>
      <Pressable style={s.quotaNudgeCta} onPress={onUpgrade}>
        <Text style={s.quotaNudgeCtaText}>{t("chat.quota_nudge_cta")}</Text>
      </Pressable>
      <Pressable onPress={onDismiss} hitSlop={8} style={s.quotaNudgeClose} accessibilityRole="button" accessibilityLabel={t("common.cancel")}>
        <Ionicons name="close" size={16} color={theme.textTertiary} />
      </Pressable>
    </View>
  );
}
