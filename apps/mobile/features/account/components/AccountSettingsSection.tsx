import { useState } from "react";
import { Linking, Platform } from "react-native";
import { useTranslation } from "react-i18next";

import { UpgradeSheet } from "@/features/billing/components/UpgradeSheet";
import {
  SettingsGroup,
  SettingsLinkRow,
  SettingsValueRow,
} from "@/features/account/components/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { planNameKey, planOf, upgradeTargets } from "@/lib/plan";

function manageSubscriptionUrl(): string {
  return Platform.OS === "ios"
    ? "https://apps.apple.com/account/subscriptions"
    : "https://play.google.com/store/account/subscriptions";
}

/**
 * Email, plan, and the Usage page. Free opens the plans sheet (which also restores a
 * purchase); a paid plan shows its name and has its own row to manage the subscription
 * in the store, and Plus also gets a way up to Pro.
 */
export function AccountSettingsSection() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const [upgradeVisible, setUpgradeVisible] = useState(false);
  const plan = planOf(user);
  const planName = t(planNameKey(plan));
  const nextPlan = plan === "free" ? null : upgradeTargets(plan)[0] ?? null;

  return (
    <>
      <SettingsGroup label={t("settings.account")}>
        <SettingsValueRow icon="mail" title={t("settings.email")} value={user?.email ?? ""} />
        {plan !== "free" ? (
          <>
            <SettingsValueRow icon="credit-card" title={t("settings.plan_label")} value={planName} />
            <SettingsLinkRow
              icon="external-link"
              title={t("settings.manage_subscription")}
              onPress={() => void Linking.openURL(manageSubscriptionUrl())}
            />
          </>
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
        <SettingsLinkRow
          icon="bar-chart"
          title={t("settings.usage_group")}
          href="/settings/usage"
        />
      </SettingsGroup>

      <UpgradeSheet
        visible={upgradeVisible}
        source="settings"
        onClose={() => setUpgradeVisible(false)}
      />
    </>
  );
}
