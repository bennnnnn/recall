import { useTranslation } from "react-i18next";

import {
  SettingsGroup,
  SettingsLinkRow,
  SettingsPage,
  SettingsValueRow,
  useSettingsAction,
} from "@/features/account/components/settingsUi";
import { openSettingsLink } from "@/features/account/model/openSettingsLink";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { appVersion, supportVersionText, versionLabel } from "@/lib/appVersion";
import { getLegalPrivacyUrl, getLegalTermsUrl } from "@/lib/legalUrls";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { useCopyText } from "@/ui/share/useCopyText";

/** Settings → About: the legal pages, the licenses, and the version. */
export default function AboutScreen() {
  const { t } = useTranslation();
  const action = useSettingsAction();
  const feedback = useActionFeedbackOptional();
  const { copy } = useCopyText(() => reportRecoverableError(feedback, t("share.copy_failed")));
  const app = appVersion();
  const open = (url: string) =>
    void action.run("link", () => openSettingsLink(url), { errorKey: "settings.link_failed" });
  // The update id means nothing to read, so it is not shown; support still gets it, from a
  // long press here and in every report Help writes.
  const copyVersion = () =>
    void copy(supportVersionText(app, t)).then((copied) => {
      if (copied) feedback?.success(t("common.copied"));
    });

  return (
    <SettingsPage>
      <SettingsGroup label={t("settings.legal")}>
        <SettingsLinkRow title={t("privacy.title")} onPress={() => open(getLegalPrivacyUrl())} />
        <SettingsLinkRow title={t("terms.title")} onPress={() => open(getLegalTermsUrl())} />
        <SettingsLinkRow
          title={t("settings.licenses")}
          href="/settings/licenses"
        />
      </SettingsGroup>

      <SettingsGroup>
        <SettingsValueRow
          title={t("settings.about_version")}
          value={versionLabel(app)}
          onLongPress={copyVersion}
          longPressLabel={t("settings.about_copy_version")}
        />
      </SettingsGroup>
    </SettingsPage>
  );
}
