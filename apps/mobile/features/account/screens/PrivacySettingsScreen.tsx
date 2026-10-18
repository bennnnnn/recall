import { useTranslation } from "react-i18next";

import {
  SettingsGroup,
  SettingsLinkRow,
  SettingsPage,
  SettingsSwitchRow,
  SettingsValueRow,
  useSettingsAction,
} from "@/features/account/components/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { getDeviceLocationLabel } from "@/lib/deviceLocation";
import { canUseDeviceLocation } from "@/lib/expoRuntime";
import { getLegalPrivacyUrl } from "@/lib/legalUrls";
import { openAllowedUrl } from "@/lib/linkSchemePolicy";
import { alertDialog } from "@/ui/overlay/dialogs";

/**
 * Settings → Privacy: what leaves the phone besides the chat itself (web
 * searches, the device location), and how the data is used.
 */
export default function PrivacySettingsScreen() {
  const { user, updateUser } = useAuth();
  const { t } = useTranslation();
  const action = useSettingsAction();

  const toggleLocation = (enabled: boolean) =>
    void action.run("location", async () => {
      if (!enabled) {
        await updateUser({ location_enabled: false, location: null });
        return;
      }
      if (!canUseDeviceLocation()) {
        void alertDialog({
          title: t("common.error"),
          message: t("settings.location_expo_go"),
        });
        return;
      }
      const label = await getDeviceLocationLabel();
      if (!label) {
        void alertDialog({ title: t("settings.location_denied") });
        return;
      }
      await updateUser({ location_enabled: true, location: label });
    });

  const locationOn = user?.location_enabled === true;

  return (
    <SettingsPage>
      <SettingsGroup>
        <SettingsSwitchRow
          icon="search"
          title={t("settings.web_search")}
          subtitle={t("settings.web_search_summary")}
          value={user?.web_search_enabled !== false}
          disabled={action.busy !== null}
          busy={action.busy === "web_search"}
          onValueChange={(next) =>
            void action.run("web_search", () =>
              updateUser({ web_search_enabled: next }),
            )
          }
        />
        <SettingsSwitchRow
          icon="map-pin"
          title={t("settings.use_current_location")}
          subtitle={
            locationOn
              ? (user?.location ?? undefined)
              : t("settings.location_summary")
          }
          value={locationOn}
          disabled={action.busy !== null}
          busy={action.busy === "location"}
          onValueChange={toggleLocation}
        />
      </SettingsGroup>

      <SettingsGroup label={t("settings.data_use_title")}>
        <SettingsValueRow title={t("settings.data_use_body")} />
        <SettingsLinkRow
          title={t("privacy.title")}
          onPress={() => void openAllowedUrl(getLegalPrivacyUrl())}
        />
      </SettingsGroup>
    </SettingsPage>
  );
}
