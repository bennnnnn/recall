import { ReactNode, useRef, type Ref } from "react";
import { StyleSheet, View } from "react-native";

import { type SettingsStyles } from "@/components/settings/settingsStyles";
import { Space } from "@/lib/space";
import type { Theme } from "@/lib/theme";
import type { IconName } from "@/ui/icons/names";
import { ListGroup } from "@/ui/list/ListGroup";
import { ListRow } from "@/ui/list/ListRow";
import { SelectMenu } from "@/ui/overlay/SelectMenu";

export { makeSettingsStyles, type SettingsStyles } from "@/components/settings/settingsStyles";

/**
 * Settings rows are the app's ListRow and ListGroup. `styles` and `theme`
 * are still accepted from older screens; the rows draw themselves now.
 */
type Legacy = { styles?: SettingsStyles; theme?: Theme };

const layout = StyleSheet.create({ section: { marginTop: Space.lg } });

export function SettingsGroup({ label, children }: { label?: string; children: ReactNode } & Legacy) {
  return (
    <ListGroup label={label} style={layout.section}>
      {children}
    </ListGroup>
  );
}

export function SettingsLinkRow({
  title,
  subtitle,
  value,
  icon,
  leading,
  danger,
  busy,
  disabled,
  onPress,
  ref,
}: {
  title: string;
  subtitle?: string;
  value?: string;
  icon?: IconName;
  leading?: ReactNode;
  danger?: boolean;
  busy?: boolean;
  disabled?: boolean;
  onPress: () => void;
  /** Lets a SelectMenu open from this row. */
  ref?: Ref<View>;
} & Legacy) {
  return (
    <ListRow
      ref={ref}
      title={title}
      subtitle={subtitle}
      value={value}
      icon={icon}
      leading={leading}
      danger={danger}
      busy={busy}
      disabled={disabled}
      onPress={onPress}
    />
  );
}

export function SettingsValueRow({
  title,
  subtitle,
  value,
  icon,
  leading,
}: {
  title: string;
  subtitle?: string;
  value?: string;
  icon?: IconName;
  leading?: ReactNode;
} & Legacy) {
  return <ListRow title={title} subtitle={subtitle} value={value} icon={icon} leading={leading} />;
}

export function SettingsInlinePicker({
  icon,
  title,
  subtitle,
  value,
  options,
  selectedKey,
  expanded,
  disabled,
  busy,
  onToggle,
  onSelect,
}: {
  icon?: IconName;
  title: string;
  subtitle?: string;
  value: string;
  options: { key: string; label: string }[];
  selectedKey: string;
  expanded: boolean;
  disabled?: boolean;
  busy?: boolean;
  onToggle: () => void;
  onSelect: (key: string) => void;
} & Legacy) {
  const rowRef = useRef<View>(null);
  // Popover only — never render options under this row (see chat-ux-bans §13).
  return (
    <View>
      <ListRow
        ref={rowRef}
        icon={icon}
        title={title}
        subtitle={subtitle}
        value={value}
        busy={busy}
        disabled={disabled}
        expanded={expanded}
        onPress={onToggle}
      />
      <SelectMenu
        visible={expanded}
        anchorRef={rowRef}
        options={options}
        selectedKey={selectedKey}
        disabled={disabled}
        onClose={onToggle}
        onSelect={onSelect}
      />
    </View>
  );
}

export function SettingsSwitchRow({
  title,
  subtitle,
  icon,
  value,
  disabled,
  busy,
  onValueChange,
}: {
  title: string;
  subtitle?: string;
  icon?: IconName;
  value: boolean;
  disabled?: boolean;
  busy?: boolean;
  onValueChange: (next: boolean) => void;
} & Legacy) {
  return (
    <ListRow
      title={title}
      subtitle={subtitle}
      icon={icon}
      switchValue={value}
      onSwitchChange={onValueChange}
      disabled={disabled}
      busy={busy}
    />
  );
}
