import { Share } from "react-native";
import Constants from "expo-constants";
import { useTranslation } from "react-i18next";

import {
  SettingsGroup,
  SettingsLinkRow,
  SettingsPage,
} from "@/features/account/components/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { planNameKey, planOf } from "@/lib/plan";
import { config } from "@/lib/config";
import { openAllowedUrl } from "@/lib/linkSchemePolicy";

/** Settings → Help: reach us, report a problem, send feedback. */
export default function HelpScreen() {
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
      <SettingsGroup>
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
    </SettingsPage>
  );
}
