import { useState } from "react";
import { Linking, Platform } from "react-native";
import { useTranslation } from "react-i18next";

import { UpgradeSheet } from "@/components/UpgradeSheet";
import {
  SettingsGroup,
  SettingsLinkRow,
  SettingsValueRow,
} from "@/features/account/components/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useLiveTalkMinutes } from "@/features/account/hooks/useLiveTalkMinutes";
import { useUsage } from "@/features/account/hooks/useUsage";
import { type User } from "@/lib/api";
import { hasPlanFeature, planNameKey, planOf, upgradeTargets } from "@/lib/plan";
import { formatUsageSummary } from "@/lib/quota";

function manageSubscriptionUrl(): string {
  return Platform.OS === "ios"
    ? "https://apps.apple.com/account/subscriptions"
    : "https://play.google.com/store/account/subscriptions";
}

function signInLabel(
  provider: User["sign_in_provider"] | undefined,
  t: (key: string) => string,
): string {
  if (provider === "google") return t("settings.sign_in_google");
  if (provider === "apple") return t("settings.sign_in_apple");
  return t("settings.sign_in_dev");
}

/**
 * Email (with how you sign in), plan, live talk minutes and today's usage.
 * Free opens the plans sheet (which also restores a purchase); a paid plan
 * manages its subscription in the store, and Plus also gets a way up to Pro.
 */
export function AccountSettingsSection({ isPaid }: { isPaid: boolean }) {
  const { user } = useAuth();
  const { t } = useTranslation();
  const { usage, loading: usageLoading, error: usageError, refresh: refreshUsage } = useUsage();
  const [upgradeVisible, setUpgradeVisible] = useState(false);
  const plan = planOf(user);
  const planName = t(planNameKey(plan));
  const nextPlan = plan === "free" ? null : upgradeTargets(plan)[0] ?? null;
  const liveTalk = useLiveTalkMinutes(hasPlanFeature(user, "live_talk"));
  // Live talk's monthly minutes sit under today's usage, not in a row of their own.
  const liveTalkLine = liveTalk
    ? t("settings.usage_live_talk", { count: liveTalk.remaining, limit: liveTalk.limit })
    : undefined;

  return (
    <>
      <SettingsGroup label={t("settings.account")}>
        <SettingsValueRow
          icon="mail"
          title={t("settings.email")}
          value={user?.email ?? ""}
          subtitle={t("settings.signed_in_with", {
            provider: signInLabel(user?.sign_in_provider, t),
          })}
        />
        {plan !== "free" ? (
          <SettingsLinkRow
            icon="credit-card"
            title={t("settings.plan_label")}
            value={planName}
            subtitle={t("settings.manage_subscription")}
            onPress={() => void Linking.openURL(manageSubscriptionUrl())}
          />
        ) : (
          <SettingsLinkRow
            icon="sparkles"
            title={t("settings.plan_label")}
            value={planName}
            onPress={() => setUpgradeVisible(true)}
            accent
          />
        )}
        {nextPlan ? (
          <SettingsLinkRow
            icon="sparkles"
            title={t("settings.plan_upgrade", { plan: t(planNameKey(nextPlan)) })}
            subtitle={t("settings.plan_upgrade_live_talk")}
            onPress={() => setUpgradeVisible(true)}
            accent
          />
        ) : null}
        {/* Never a blank row: today's share, "…" while it loads, or a retry. */}
        {usage || !usageError ? (
          <SettingsValueRow
            icon="bar-chart"
            title={t("settings.usage_group")}
            value={usage ? formatUsageSummary(usage, isPaid, t) : usageLoading ? "…" : undefined}
            subtitle={liveTalkLine}
          />
        ) : (
          <SettingsLinkRow
            icon="bar-chart"
            title={t("settings.usage_group")}
            value={t("settings.usage_unavailable")}
            subtitle={liveTalkLine}
            onPress={() => void refreshUsage({ force: true })}
          />
        )}
      </SettingsGroup>

      <UpgradeSheet
        visible={upgradeVisible}
        source="settings"
        onClose={() => setUpgradeVisible(false)}
      />
    </>
  );
}
