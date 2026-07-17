import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { tap } from "@/lib/haptics";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

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
        <Button
          title={resolvedRetryLabel ?? t("common.retry")}
          onPress={() => {
            tap();
            onRetry();
          }}
          style={s.retryBtn}
        />
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
      ...Type.secondary,
      color: theme.textSecondary,
      textAlign: "center",
    },
    retryBtn: {
      marginTop: 8,
      alignSelf: "center",
      paddingHorizontal: 24,
    },
  });
}
