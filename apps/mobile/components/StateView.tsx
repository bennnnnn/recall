import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { Theme, useTheme } from "@/lib/theme";
import { tap } from "@/lib/haptics";

type IconName = keyof typeof Ionicons.glyphMap;

type Props = {
  variant: "loading" | "error" | "empty";
  title?: string;
  message?: string;
  icon?: IconName;
  onRetry?: () => void;
  retryLabel?: string;
  compact?: boolean;
};

export function StateView({
  variant,
  title,
  message,
  icon,
  onRetry,
  retryLabel,
  compact = false,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = makeStyles(theme, compact);
  const resolvedRetryLabel = retryLabel ?? (onRetry ? t("common.retry") : undefined);

  if (variant === "loading") {
    return (
      <View style={s.wrap}>
        <ActivityIndicator size={compact ? "small" : "large"} color={theme.primary} />
      </View>
    );
  }

  const defaultIcon: IconName =
    variant === "error" ? "cloud-offline-outline" : "folder-open-outline";

  return (
    <View style={s.wrap}>
      <Ionicons
        name={icon ?? defaultIcon}
        size={compact ? 32 : 48}
        color={theme.textTertiary}
        style={s.icon}
      />
      {title ? <Text style={s.title}>{title}</Text> : null}
      {message ? <Text style={s.message}>{message}</Text> : null}
      {onRetry ? (
        <Pressable
          style={s.retryBtn}
          onPress={() => {
            tap();
            onRetry();
          }}
        >
          <Text style={s.retryText}>{resolvedRetryLabel}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

function makeStyles(theme: Theme, compact: boolean) {
  return StyleSheet.create({
    wrap: {
      flex: compact ? undefined : 1,
      alignItems: "center",
      justifyContent: "center",
      paddingVertical: compact ? 24 : 40,
      paddingHorizontal: 24,
      gap: 8,
    },
    icon: { marginBottom: 4 },
    title: {
      fontSize: 17,
      fontWeight: "700",
      color: theme.text,
      textAlign: "center",
    },
    message: {
      fontSize: 15,
      lineHeight: 22,
      color: theme.textSecondary,
      textAlign: "center",
    },
    retryBtn: {
      marginTop: 8,
      paddingHorizontal: 20,
      paddingVertical: 10,
      borderRadius: 10,
      backgroundColor: theme.primary,
    },
    retryText: { fontSize: 14, fontWeight: "600", color: theme.onPrimary },
  });
}
