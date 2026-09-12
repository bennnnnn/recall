import { useMemo } from "react";
import { ActivityIndicator, ScrollView, Text, View } from "react-native";
import { Redirect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { StateView } from "@/components/StateView";
import { makeSettingsStyles, SettingsGroup } from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useUsage } from "@/hooks/useUsage";
import {
  formatTokenCount,
  formatUsageSummary,
  usageUsedPercent,
  usageUsedTokens,
} from "@/lib/quota";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

export default function UsageSettingsScreen() {
  const { token, user } = useAuth();
  const { usage, error, refresh } = useUsage();
  const { t } = useTranslation();
  const theme = useTheme();
  const styles = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();

  if (!token) return <Redirect href="/login" />;

  const usedPercent = usage ? Math.max(0, Math.round(usageUsedPercent(usage))) : null;
  const usedLabel = usage
    ? t("settings.usage_today_value", {
        used: formatTokenCount(usageUsedTokens(usage)),
        limit: formatTokenCount(usage.daily_limit),
      })
    : undefined;

  return (
    <ScrollView
      style={styles.scroll}
      contentContainerStyle={[
        styles.content,
        { paddingBottom: insets.bottom + Space.lg },
      ]}
    >
      <SettingsGroup label={t("settings.usage_today")} styles={styles}>
        {error ? (
          <StateView
            variant="error"
            compact
            message={t("common.error")}
            onRetry={() => void refresh({ force: true })}
          />
        ) : (
          <View style={styles.menuRow}>
            <View style={styles.rowBody}>
              <Text style={styles.rowTitle}>{t("settings.usage_daily")}</Text>
              {usage && usedPercent !== null ? (
                <>
                  <Text style={styles.meta}>{usedLabel}</Text>
                  <View
                    style={styles.usageTrack}
                    accessible
                    accessibilityRole="progressbar"
                    accessibilityLabel={t("settings.usage_daily")}
                    accessibilityValue={{ min: 0, max: 100, now: usedPercent, text: usedLabel }}
                  >
                    <View style={[styles.usageFill, { width: `${usedPercent}%` }]} />
                  </View>
                  <Text style={styles.meta}>
                    {formatUsageSummary(usage, user?.plan === "pro", t)}
                  </Text>
                </>
              ) : (
                <ActivityIndicator
                  color={theme.primary}
                  accessible
                  accessibilityRole="progressbar"
                  accessibilityLabel={t("settings.usage_daily")}
                  accessibilityState={{ busy: true }}
                />
              )}
            </View>
          </View>
        )}
      </SettingsGroup>
    </ScrollView>
  );
}
