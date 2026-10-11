import { type ReactNode, type Ref } from "react";
import { StyleSheet, type View } from "react-native";

import { Space } from "@/lib/space";
import type { IconName } from "@/ui/icons/names";
import { ListGroup } from "@/ui/list/ListGroup";
import { ListRow } from "@/ui/list/ListRow";

type SettingsOverviewGroupProps = {
  label?: string;
  children: ReactNode;
};

type SettingsOverviewRowProps = {
  icon: IconName;
  title: string;
  value?: string;
  onPress?: () => void;
  accessibilityHint?: string;
  expanded?: boolean;
  danger?: boolean;
  accent?: boolean;
  /** Lets a SelectMenu open from this row. */
  ref?: Ref<View>;
};

const layout = StyleSheet.create({ section: { marginTop: Space.lg } });

export function SettingsOverviewGroup({ label, children }: SettingsOverviewGroupProps) {
  return (
    <ListGroup label={label} spaced style={layout.section}>
      {children}
    </ListGroup>
  );
}

export function SettingsOverviewRow({
  icon,
  title,
  value,
  onPress,
  accessibilityHint,
  expanded,
  danger,
  accent,
  ref,
}: SettingsOverviewRowProps) {
  return (
    <ListRow
      ref={ref}
      icon={icon}
      title={title}
      value={value}
      danger={danger}
      accent={accent}
      expanded={expanded}
      onPress={onPress}
      accessibilityLabel={value ? `${title}, ${value}` : title}
      accessibilityHint={accessibilityHint}
    />
  );
}
