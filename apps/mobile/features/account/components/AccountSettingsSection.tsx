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
import { useLibraryStorage } from "@/features/attachments/hooks/useLibraryStorage";
import { storageUsedOfTotal } from "@/features/attachments/model/storageSize";
import { planNameKey, planOf } from "@/lib/plan";

function manageSubscriptionUrl(): string {
  return Platform.OS === "ios"
    ? "https://apps.apple.com/account/subscriptions"
    : "https://play.google.com/store/account/subscriptions";
}

/**
 * Email, plan, the Usage page, and Storage: what the Library keeps of the plan's total,
 * opening Library, where files are deleted. Free opens the plans page (which also restores a
 * purchase); the paid plan shows its name and has its own row to manage the subscription
 * in the store.
 */
export function AccountSettingsSection() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const [upgradeVisible, setUpgradeVisible] = useState(false);
  const plan = planOf(user);
  const planName = t(planNameKey(plan));
  const storage = useLibraryStorage();

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
        <SettingsLinkRow
          icon="bar-chart"
          title={t("settings.usage_group")}
          href="/settings/usage"
        />
        <SettingsLinkRow
          icon="hard-drive"
          title={t("settings.storage")}
          value={
            storage
              ? storageUsedOfTotal(storage.usedBytes, storage.limitBytes, user?.locale ?? "en", t)
              : undefined
          }
          href="/gallery"
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
