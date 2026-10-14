import { useTranslation } from "react-i18next";

import { StateView } from "@/ui/feedback/StateView";
import { BrandMark } from "@/ui/icons/brand";
import { IconSize } from "@/ui/icons/sizes";
import { ConnectedAppCard } from "@/features/account/components/ConnectedAppCard";
import { SettingsLinkRow, SettingsPage } from "@/features/account/components/settingsUi";
import { useSettingsIntegrations } from "@/features/integrations/hooks/useSettingsIntegrations";

export default function ConnectedAppsScreen() {
  const { t } = useTranslation();
  const {
    calendarStatus, calendarBusy, gmailStatus, gmailBusy, loading, loadError,
    connectCalendar, disconnectCalendar, connectGmail, disconnectGmail, syncGmail, refresh,
  } = useSettingsIntegrations();

  const statusLabel = (status: { connected: boolean; email?: string | null } | null) =>
    !status ? undefined : status.connected
      ? status.email || t("settings.integration_connected")
      : t("settings.integration_not_connected");
  const actionsDisabled = loading || calendarBusy || gmailBusy;
  const calendarPending = calendarBusy || (!calendarStatus && !loadError);
  const gmailPending = gmailBusy || (!gmailStatus && !loadError);
  const lastSync = gmailStatus?.connected && gmailStatus.last_sync_at
    ? t("settings.gmail_last_sync", { when: new Date(gmailStatus.last_sync_at).toLocaleString() })
    : undefined;

  return (
    <SettingsPage>
      {loadError ? (
        <StateView
          variant="error"
          compact
          message={t("common.error")}
          onRetry={() => void refresh()}
          retryLabel={t("common.retry")}
        />
      ) : null}
      <ConnectedAppCard
        leading={<BrandMark name="google" size={IconSize.md} />}
        title={t("settings.calendar_title")}
        description={!calendarStatus?.connected ? t("settings.calendar_desc") : undefined}
        value={statusLabel(calendarStatus)}
        actionLabel={t(calendarStatus?.connected ? "settings.calendar_disconnect" : "settings.calendar_connect")}
        onAction={calendarStatus?.connected ? disconnectCalendar : () => void connectCalendar(false)}
        busy={calendarPending}
        disabled={actionsDisabled || !calendarStatus}
      >
        {calendarStatus?.connected && !calendarStatus.can_write ? (
          <SettingsLinkRow
            title={t("settings.calendar_upgrade_write")}
            onPress={() => void connectCalendar(true)}
            disabled={actionsDisabled}
          />
        ) : null}
      </ConnectedAppCard>
      <ConnectedAppCard
        leading={<BrandMark name="gmail" size={IconSize.md} />}
        title={t("settings.gmail_title")}
        description={!gmailStatus?.connected ? t("settings.gmail_desc") : undefined}
        value={statusLabel(gmailStatus)}
        actionLabel={t(gmailStatus?.connected ? "settings.gmail_disconnect" : "settings.calendar_connect")}
        onAction={gmailStatus?.connected ? disconnectGmail : connectGmail}
        busy={gmailPending}
        disabled={actionsDisabled || !gmailStatus}
      >
        {gmailStatus?.connected ? (
          <SettingsLinkRow
            title={t("settings.gmail_sync")}
            subtitle={lastSync}
            onPress={() => void syncGmail()}
            disabled={actionsDisabled}
          />
        ) : null}
      </ConnectedAppCard>
    </SettingsPage>
  );
}
