import { useMemo } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

/** Preserve a recoverable startup failure instead of showing a signed-out app. */
export function AuthLoadingShell({ failed, onRetry }: { failed: boolean; onRetry: () => void }) {
  const theme = useTheme();
  const { t } = useTranslation();
  const styles = useMemo(() => StyleSheet.create({
    shell: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      padding: Space.xl,
      gap: Space.md,
      backgroundColor: theme.bg,
    },
    message: { ...Type.body, color: theme.text, textAlign: "center" },
  }), [theme]);
  return (
    <View style={styles.shell}>
      {failed ? <>
        <Text accessibilityRole="alert" style={styles.message}>{t("login.error_generic")}</Text>
        <Button title={t("common.retry")} onPress={onRetry} />
      </> : <ActivityIndicator size="large" color={theme.primary} />}
    </View>
  );
}
