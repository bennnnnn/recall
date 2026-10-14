import type { ReactNode } from "react";

import { SettingsGroup } from "@/features/account/components/settingsUi";
import { ListRow } from "@/ui/list/ListRow";

/**
 * One connected service: its logo, status and a Connect/Disconnect capsule
 * (the whole row presses it), with extra rows such as Sync under it.
 */
export function ConnectedAppCard({
  title,
  description,
  value,
  leading,
  actionLabel,
  onAction,
  busy,
  disabled,
  children,
}: {
  title: string;
  description?: string;
  value?: string;
  leading: ReactNode;
  actionLabel: string;
  onAction: () => void;
  busy: boolean;
  disabled: boolean;
  children?: ReactNode;
}) {
  return (
    <SettingsGroup>
      <ListRow
        leading={leading}
        title={title}
        value={value}
        subtitle={description}
        detail={actionLabel}
        detailStyle="pill"
        busy={busy}
        disabled={disabled}
        onPress={onAction}
        accessibilityLabel={`${actionLabel} ${title}`}
        accessibilityHint={value}
      />
      {children}
    </SettingsGroup>
  );
}
