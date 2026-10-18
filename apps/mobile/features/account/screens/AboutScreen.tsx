import Constants from "expo-constants";
import { useTranslation } from "react-i18next";

import {
  SettingsGroup,
  SettingsLinkRow,
  SettingsPage,
  SettingsValueRow,
} from "@/features/account/components/settingsUi";
import { getLegalPrivacyUrl, getLegalTermsUrl } from "@/lib/legalUrls";
import { openAllowedUrl } from "@/lib/linkSchemePolicy";

/** Settings → About: the legal pages, the licenses, and the version. */
export default function AboutScreen() {
  const { t } = useTranslation();
  const version = Constants.expoConfig?.version ?? "1.0.0";

  return (
    <SettingsPage>
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
    </SettingsPage>
  );
}
