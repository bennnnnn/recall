import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Image,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import type { PendingAttachment } from "@/lib/attachments";
import { Theme, withAlpha } from "@/lib/theme";

type OcrStatus = "idle" | "loading" | "done" | "failed";

type Props = {
  preview: PendingAttachment;
  ocrStatus: OcrStatus;
  reading: string;
  uncertain: boolean;
  onChangeReading: (value: string) => void;
  onClose: () => void;
  onRetake: () => void;
  onSolve: () => void;
  solveWaiting: boolean;
  theme: Theme;
};

export function MathScanConfirmView({
  preview,
  ocrStatus,
  reading,
  uncertain,
  onChangeReading,
  onClose,
  onRetake,
  onSolve,
  solveWaiting,
  theme,
}: Props) {
  const { t } = useTranslation();
  const insets = useSafeAreaInsets();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    if (ocrStatus === "done" && reading) setEditing(false);
  }, [ocrStatus, reading]);

  const showReading = ocrStatus === "done" && Boolean(reading.trim());

  return (
    <KeyboardAvoidingView
      style={s.previewRoot}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <Image source={{ uri: preview.localUri }} style={s.previewImage} resizeMode="contain" />
      <Pressable
        style={[s.close, { top: insets.top + 8 }]}
        onPress={onClose}
        hitSlop={12}
        accessibilityRole="button"
        accessibilityLabel={t("common.close")}
      >
        <Icon name="close" size={28} color={theme.onMedia} />
      </Pressable>
      <View style={[s.readCard, { paddingBottom: Math.max(insets.bottom, 16) + 12 }]}>
        {ocrStatus === "loading" ? (
          <View style={s.readingRow}>
            <ActivityIndicator color={theme.onMedia} />
            <Text style={s.hint}>{t("chat.math_scan_reading")}</Text>
          </View>
        ) : null}
        {ocrStatus === "failed" ? (
          <Text style={s.hint}>{t("chat.math_scan_read_failed")}</Text>
        ) : null}
        {showReading ? (
          <>
            <Text style={s.readLabel}>{t("chat.math_scan_read_as")}</Text>
            {editing ? (
              <TextInput
                value={reading}
                onChangeText={onChangeReading}
                style={s.readInput}
                multiline
                autoFocus
                placeholder={t("chat.math_scan_read_as")}
                placeholderTextColor={withAlpha(theme.onMedia, 0.45)}
                accessibilityLabel={t("chat.math_scan_read_as")}
              />
            ) : (
              <Text style={[s.readText, uncertain ? s.readUncertain : null]}>{reading}</Text>
            )}
            <Pressable
              onPress={() => setEditing((open) => !open)}
              accessibilityRole="button"
              accessibilityLabel={t("chat.math_scan_edit")}
              hitSlop={8}
            >
              <Text style={s.edit}>{t("chat.math_scan_edit")}</Text>
            </Pressable>
          </>
        ) : null}
        <View style={s.previewActions}>
          <Pressable
            style={s.previewSecondary}
            onPress={onRetake}
            accessibilityRole="button"
            accessibilityLabel={t("chat.math_scan_retake")}
          >
            <Text style={s.previewSecondaryText}>{t("chat.math_scan_retake")}</Text>
          </Pressable>
          <Pressable
            style={s.previewPrimary}
            onPress={onSolve}
            accessibilityRole="button"
            accessibilityLabel={t("chat.math_scan_solve")}
          >
            {solveWaiting ? (
              <ActivityIndicator color={theme.onPrimary} />
            ) : (
              <Text style={s.previewPrimaryText}>{t("chat.math_scan_solve")}</Text>
            )}
          </Pressable>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    previewRoot: {
      flex: 1,
      backgroundColor: theme.mediaScrim,
    },
    previewImage: {
      flex: 1,
      width: "100%",
      marginTop: 72,
      marginBottom: 8,
    },
    close: {
      position: "absolute",
      left: 16,
      width: 40,
      height: 40,
      borderRadius: 20,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: withAlpha(theme.mediaScrim, 0.55),
      zIndex: 10,
    },
    readCard: {
      paddingHorizontal: 16,
      gap: 8,
    },
    readingRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      alignSelf: "center",
    },
    hint: {
      color: theme.onMedia,
      fontSize: 14,
      fontWeight: "600",
      textAlign: "center",
    },
    readLabel: {
      color: withAlpha(theme.onMedia, 0.8),
      fontSize: 13,
      fontWeight: "600",
      textAlign: "center",
    },
    readText: {
      color: theme.onMedia,
      fontSize: 20,
      fontWeight: "700",
      textAlign: "center",
      lineHeight: 26,
    },
    readUncertain: {
      color: theme.warning,
    },
    readInput: {
      color: theme.onMedia,
      fontSize: 18,
      fontWeight: "700",
      textAlign: "center",
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: withAlpha(theme.onMedia, 0.4),
      paddingVertical: 8,
    },
    edit: {
      color: theme.primary,
      fontSize: 15,
      fontWeight: "700",
      textAlign: "center",
      paddingVertical: 4,
    },
    previewActions: {
      flexDirection: "row",
      gap: 12,
      marginTop: 8,
    },
    previewSecondary: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      paddingVertical: 14,
      borderRadius: 12,
      backgroundColor: withAlpha(theme.onMedia, 0.18),
      minHeight: 48,
    },
    previewSecondaryText: {
      color: theme.onMedia,
      fontSize: 16,
      fontWeight: "700",
    },
    previewPrimary: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      paddingVertical: 14,
      borderRadius: 12,
      backgroundColor: theme.primary,
      minHeight: 48,
    },
    previewPrimaryText: {
      color: theme.onPrimary,
      fontSize: 16,
      fontWeight: "700",
    },
  });
}
