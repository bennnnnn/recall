import { Share } from "react-native";
import Constants from "expo-constants";
import { useTranslation } from "react-i18next";

import {
  SettingsGroup,
  SettingsLinkRow,
  SettingsPage,
  SettingsValueRow,
} from "@/features/account/components/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { planNameKey, planOf } from "@/lib/plan";
import { config } from "@/lib/config";
import { getLegalPrivacyUrl, getLegalTermsUrl } from "@/lib/legalUrls";
import { openAllowedUrl } from "@/lib/linkSchemePolicy";

/** Settings → Help & about: reach us, the legal pages, and the version. */
export default function AboutScreen() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const version = Constants.expoConfig?.version ?? "1.0.0";

  /** What support needs to know, without anything from the user's chats. */
  const reportBody = (title: string) =>
    [
      title,
      "",
      `${t("settings.about_version")}: ${version}`,
      `${t("settings.plan_label")}: ${t(planNameKey(planOf(user)))}`,
      `${t("settings.language")}: ${user?.locale ?? "en"}`,
    ].join("\n");

  const share = (titleKey: string) => {
    const title = t(titleKey);
    void Share.share({ title, message: reportBody(title) });
  };

  const contactSupport = (email: string) => {
    const subject = encodeURIComponent(t("settings.contact_support_subject"));
    const body = encodeURIComponent(reportBody(t("settings.contact_support")));
    void openAllowedUrl(`mailto:${email}?subject=${subject}&body=${body}`);
  };

  const supportEmail = config.supportEmail;

  return (
    <SettingsPage>
      <SettingsGroup label={t("settings.support")}>
        {supportEmail ? (
          <SettingsLinkRow
            title={t("settings.contact_support")}
            value={supportEmail}
            onPress={() => contactSupport(supportEmail)}
          />
        ) : null}
        <SettingsLinkRow
          title={t("settings.report_problem")}
          onPress={() => share("settings.report_problem")}
        />
        <SettingsLinkRow
          title={t("settings.send_feedback")}
          onPress={() => share("settings.send_feedback")}
        />
      </SettingsGroup>

      <SettingsGroup label={t("settings.legal")}>
        <SettingsLinkRow
          title={t("privacy.title")}
          onPress={() => void openAllowedUrl(getLegalPrivacyUrl())}
        />
        <SettingsLinkRow
          title={t("terms.title")}
          onPress={() => void openAllowedUrl(getLegalTermsUrl())}
        />
        <SettingsLinkRow
          title={t("settings.licenses")}
          href="/settings/licenses"
        />
      </SettingsGroup>

      <SettingsGroup>
        <SettingsValueRow title={t("settings.about_version")} value={version} />
      </SettingsGroup>

      {__DEV__ ? (
        <SettingsGroup>
          <SettingsLinkRow icon="grid" title="UI kit" href="/dev-ui" />
        </SettingsGroup>
      ) : null}
    </SettingsPage>
  );
}
