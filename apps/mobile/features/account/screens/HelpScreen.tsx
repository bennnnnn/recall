import { Text } from "react-native";
import { useTranslation } from "react-i18next";

import {
  SettingsGroup,
  SettingsLinkRow,
  SettingsPage,
  useSettingsAction,
} from "@/features/account/components/settingsUi";
import { openSettingsLink } from "@/features/account/model/openSettingsLink";
import { useAuth } from "@/contexts/AuthContext";
import { appVersion, versionLabel } from "@/lib/appVersion";
import { planNameKey, planOf } from "@/lib/plan";
import { config } from "@/lib/config";
import { useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

/**
 * Settings → Help: write to support, report a problem, send feedback. Each is an email
 * to the configured support address; a build without one says so instead of opening
 * a share sheet that reaches nobody.
 */
export default function HelpScreen() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const action = useSettingsAction();
  const app = appVersion();

  /** What support needs to know, without anything from the user's chats. */
  const reportBody = (title: string) =>
    [
      title,
      "",
      `${t("settings.about_version")}: ${versionLabel(app)}`,
      ...(app.update ? [`${t("settings.about_update")}: ${app.update}`] : []),
      `${t("settings.plan_label")}: ${t(planNameKey(planOf(user)))}`,
      `${t("settings.language")}: ${user?.locale ?? "en"}`,
    ].join("\n");

  const write = (email: string, titleKey: string) => {
    const title = t(titleKey);
    const subject = encodeURIComponent(`${t("settings.contact_support_subject")}: ${title}`);
    const body = encodeURIComponent(reportBody(title));
    void action.run("mail", () => openSettingsLink(`mailto:${email}?subject=${subject}&body=${body}`), {
      errorKey: "settings.link_failed",
    });
  };

  const supportEmail = config.supportEmail;

  return (
    <SettingsPage>
      {supportEmail ? (
        <SettingsGroup>
          <SettingsLinkRow
            title={t("settings.contact_support")}
            value={supportEmail}
            onPress={() => write(supportEmail, "settings.contact_support")}
          />
          <SettingsLinkRow
            title={t("settings.report_problem")}
            onPress={() => write(supportEmail, "settings.report_problem")}
          />
          <SettingsLinkRow
            title={t("settings.send_feedback")}
            onPress={() => write(supportEmail, "settings.send_feedback")}
          />
        </SettingsGroup>
      ) : (
        <Text style={{ ...Type.secondary, color: theme.textSecondary }}>{t("settings.support_unavailable")}</Text>
      )}
    </SettingsPage>
  );
}
