import { useMemo } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useTranslation } from "react-i18next";
import { setStringAsync } from "expo-clipboard";

import { Sheet } from "@/ui/overlay/Sheet";
import { Icon } from "@/ui/icons/Icon";
import { tap } from "@/lib/haptics";
import { presentShareSheet } from "@/lib/share";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { IconSize } from "@/ui/icons/sizes";

type Props = {
  visible: boolean;
  loading: boolean;
  letter: string | null;
  onClose: () => void;
};

export function CoverLetterSheet({ visible, loading, letter, onClose }: Props) {
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const { t } = useTranslation();

  const copy = async () => {
    if (!letter) return;
    tap();
    await setStringAsync(letter);
  };

  const share = async () => {
    if (!letter) return;
    tap();
    // Keep the sheet mounted until the OS share UI returns — closing the RN
    // Modal first makes iOS drop the activity sheet.
    try {
      await presentShareSheet({ message: letter });
    } catch {
      Alert.alert(t("common.share_failed"), t("my_job.share_failed"));
    }
  };

  return (
    <Sheet visible={visible} onClose={onClose} withHandle>
      <View style={s.header}>
        <Text style={s.headerTitle}>{t("my_job.cover_letter_title")}</Text>
        <Pressable
          style={({ pressed }) => [s.closeButton, pressed && s.pressed]}
          onPress={onClose}
          accessibilityRole="button"
          accessibilityLabel={t("common.close")}
        >
          <Icon name="close" size={IconSize.sm} color={C.textSecondary} />
        </Pressable>
      </View>
      {loading ? (
        <View style={s.loading}>
          <ActivityIndicator color={C.primary} />
          <Text style={s.loadingText}>{t("my_job.cover_letter_generating")}</Text>
        </View>
      ) : letter ? (
        <View style={s.body}>
          <ScrollView style={s.letterScroll} showsVerticalScrollIndicator={false}>
            <Text style={s.letter} selectable>
              {letter}
            </Text>
          </ScrollView>
          <View style={s.actions}>
            <Pressable
              style={({ pressed }) => [s.action, pressed && s.pressed]}
              onPress={() => void copy()}
              accessibilityRole="button"
            >
              <Icon name="copy" size={IconSize.sm} color={C.textSecondary} />
              <Text style={s.actionText}>{t("common.copy")}</Text>
            </Pressable>
            <Pressable
              style={({ pressed }) => [s.action, s.actionPrimary, pressed && s.pressed]}
              onPress={() => void share()}
              accessibilityRole="button"
            >
              <Icon name="share" size={IconSize.sm} color={C.onPrimary} />
              <Text style={[s.actionText, s.actionTextPrimary]}>
                {t("my_job.cover_letter_share")}
              </Text>
            </Pressable>
          </View>
        </View>
      ) : null}
    </Sheet>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    header: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      marginBottom: Space.sm,
    },
    headerTitle: { ...Type.navTitle, color: C.text, ...Weight.bold },
    closeButton: {
      width: Space.minTouch,
      height: Space.minTouch,
      borderRadius: Space.minTouch / 2,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: C.surfaceAlt,
    },
    loading: {
      alignItems: "center",
      justifyContent: "center",
      gap: Space.sm,
      paddingVertical: Space.xl,
    },
    loadingText: { ...Type.secondary, color: C.textSecondary },
    body: { gap: Space.sm },
    letterScroll: { maxHeight: 420 },
    letter: { ...Type.body, color: C.text },
    actions: { flexDirection: "row", gap: Space.xs },
    action: {
      minHeight: 44,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: Space.xxs,
      paddingHorizontal: Space.md,
      borderRadius: Radius.full,
      backgroundColor: C.surfaceAlt,
    },
    actionPrimary: { backgroundColor: C.primary, flexGrow: 1 },
    actionText: { ...Type.secondary, color: C.textSecondary, ...Weight.semibold },
    actionTextPrimary: { color: C.onPrimary },
    pressed: { opacity: 0.68 },
  });
}
