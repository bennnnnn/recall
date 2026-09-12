import { useState } from "react";
import { Linking, Platform } from "react-native";
import { useTranslation } from "react-i18next";

import { UpgradeSheet } from "@/components/UpgradeSheet";
import {
  SettingsOverviewGroup,
  SettingsOverviewRow,
} from "@/components/settings/SettingsOverview";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { type User } from "@/lib/api";
import { restorePurchases } from "@/lib/purchases";

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

export function AccountSettingsSection({ isPro }: { isPro: boolean }) {
  const { user } = useAuth();
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();

  const [upgradeVisible, setUpgradeVisible] = useState(false);
  const [restoreBusy, setRestoreBusy] = useState(false);

  const restore = async () => {
    if (restoreBusy) return;
    setRestoreBusy(true);
    try {
      const ok = await restorePurchases();
      if (ok) {
        feedback?.success(t("settings.restore_purchases_ok"));
      } else {
        feedback?.error(t("settings.restore_purchases_none"));
      }
    } catch {
      feedback?.error(t("common.error"));
    } finally {
      setRestoreBusy(false);
    }
  };

  const planLabel = isPro ? t("settings.account_pro") : t("settings.account_free");

  return (
    <>
      <SettingsOverviewGroup label={t("settings.account")}>
        <SettingsOverviewRow
          icon="mail-outline"
          title={t("settings.email")}
          value={user?.email ?? ""}
        />
        <SettingsOverviewRow
          icon="key-outline"
          title={t("settings.sign_in_method")}
          value={signInLabel(user?.sign_in_provider, t)}
        />
        {isPro ? (
          <>
            <SettingsOverviewRow
              icon="card-outline"
              title={t("settings.plan_label")}
              value={planLabel}
            />
            <SettingsOverviewRow
              icon="wallet-outline"
              title={t("settings.manage_subscription")}
              onPress={() => void Linking.openURL(manageSubscriptionUrl())}
            />
            <SettingsOverviewRow
              icon="refresh-outline"
              title={t("settings.restore_purchases")}
              onPress={() => void restore()}
            />
          </>
        ) : (
          <SettingsOverviewRow
            icon="sparkles-outline"
            title={t("settings.plan_label")}
            value={planLabel}
            onPress={() => setUpgradeVisible(true)}
            accent
          />
        )}
      </SettingsOverviewGroup>

      <UpgradeSheet
        visible={upgradeVisible}
        source="settings"
        onClose={() => setUpgradeVisible(false)}
      />
    </>
  );
}
