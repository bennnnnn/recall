import { ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  Switch,
  Text,
  View,
} from "react-native";
import { Icon } from "@/components/Icon";
import { SettingsPickerSheet } from "@/components/settings/SettingsPickerSheet";
import { type SettingsStyles } from "@/components/settings/settingsStyles";
import { type IoniconName } from "@/lib/icons";
import { Theme } from "@/lib/theme";

export { makeSettingsStyles, type SettingsStyles } from "@/components/settings/settingsStyles";

export function SettingsGroup({
  label,
  children,
  styles,
}: {
  label?: string;
  children: ReactNode;
  styles: SettingsStyles;
}) {
  return (
    <View style={styles.section}>
      {label ? <Text style={styles.sectionLabel}>{label}</Text> : null}
      <View style={styles.footerGroup}>{children}</View>
    </View>
  );
}

function SettingsRowChrome({
  icon,
  leading,
  title,
  subtitle,
  value,
  chevron,
  busy,
  danger,
  styles,
  theme,
}: {
  icon?: IoniconName;
  leading?: ReactNode;
  title: string;
  subtitle?: string;
  value?: string;
  chevron?: "down" | "up";
  busy?: boolean;
  danger?: boolean;
  styles: SettingsStyles;
  theme: Theme;
}) {
  return (
    <>
      {leading || icon ? (
        <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          {leading ?? (icon ? <Icon name={icon} size={26} danger={danger} /> : null)}
        </View>
      ) : null}
      <View style={styles.rowBody}>
        <Text style={[styles.rowTitle, danger && { color: theme.danger }]}>
          {title}
        </Text>
        {value ? <Text style={styles.linkValue}>{value}</Text> : null}
        {subtitle ? <Text style={styles.meta}>{subtitle}</Text> : null}
      </View>
      {busy || chevron ? (
        <View
          style={styles.linkTrailing}
          accessibilityElementsHidden
          importantForAccessibility="no-hide-descendants"
        >
          {busy ? (
            <ActivityIndicator size="small" color={theme.primary} />
          ) : chevron ? (
            <Icon name={`chevron-${chevron}`} size={18} color={theme.textTertiary} />
          ) : null}
        </View>
      ) : null}
    </>
  );
}

export function SettingsLinkRow({
  title,
  subtitle,
  value,
  icon,
  leading,
  danger,
  onPress,
  styles,
  theme,
}: {
  title: string;
  subtitle?: string;
  value?: string;
  icon?: IoniconName;
  leading?: ReactNode;
  danger?: boolean;
  onPress: () => void;
  styles: SettingsStyles;
  theme: Theme;
}) {
  return (
    <Pressable
      style={({ pressed }) => [styles.menuRow, pressed && styles.rowPressed]}
      onPress={onPress}
      accessibilityRole="button"
    >
      <SettingsRowChrome
        icon={icon}
        leading={leading}
        title={title}
        subtitle={subtitle}
        value={value}
        danger={danger}
        styles={styles}
        theme={theme}
      />
    </Pressable>
  );
}

export function SettingsValueRow({
  title,
  subtitle,
  value,
  icon,
  leading,
  styles,
  theme,
}: {
  title: string;
  subtitle?: string;
  value?: string;
  icon?: IoniconName;
  leading?: ReactNode;
  styles: SettingsStyles;
  theme: Theme;
}) {
  return (
    <View style={styles.menuRow} accessibilityRole="text">
      <SettingsRowChrome
        icon={icon}
        leading={leading}
        title={title}
        subtitle={subtitle}
        value={value}
        styles={styles}
        theme={theme}
      />
    </View>
  );
}

export function SettingsDisclosureRow({
  title,
  subtitle,
  icon,
  expanded,
  onToggle,
  styles,
  theme,
}: {
  title: string;
  subtitle?: string;
  icon?: IoniconName;
  expanded: boolean;
  onToggle: () => void;
  styles: SettingsStyles;
  theme: Theme;
}) {
  return (
    <Pressable
      style={({ pressed }) => [styles.menuRow, pressed && styles.rowPressed]}
      onPress={onToggle}
      accessibilityRole="button"
      accessibilityState={{ expanded }}
    >
      <SettingsRowChrome
        icon={icon}
        title={title}
        subtitle={subtitle}
        chevron={expanded ? "up" : "down"}
        styles={styles}
        theme={theme}
      />
    </Pressable>
  );
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
  styles,
  theme,
}: {
  icon?: IoniconName;
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
  styles: SettingsStyles;
  theme: Theme;
}) {
  // Popup only — never render options under this row (see chat-ux-bans §13).
  return (
    <View>
      <Pressable
        style={({ pressed }) => [styles.menuRow, pressed && styles.rowPressed]}
        onPress={onToggle}
        disabled={disabled}
        accessibilityRole="button"
        accessibilityState={{ expanded, disabled: Boolean(disabled), busy: Boolean(busy) }}
      >
        <SettingsRowChrome
          icon={icon}
          title={title}
          subtitle={subtitle}
          value={value}
          busy={busy}
          styles={styles}
          theme={theme}
        />
      </Pressable>
      <SettingsPickerSheet
        visible={expanded}
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
  styles,
  theme,
}: {
  title: string;
  subtitle?: string;
  icon?: IoniconName;
  value: boolean;
  disabled?: boolean;
  busy?: boolean;
  onValueChange: (next: boolean) => void;
  styles: SettingsStyles;
  theme: Theme;
}) {
  const body = (
    <>
      {icon ? (
        <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          <Icon name={icon} size={26} />
        </View>
      ) : null}
      <View style={styles.rowBody}>
        <Text style={styles.rowTitle}>{title}</Text>
        {subtitle ? <Text style={styles.meta}>{subtitle}</Text> : null}
      </View>
      {busy ? (
        <View
          accessible
          accessibilityRole="progressbar"
          accessibilityState={{ busy: true }}
        >
          <ActivityIndicator size="small" color={theme.primary} />
        </View>
      ) : (
        <Switch
          value={value}
          disabled={disabled}
          thumbColor={theme.bg}
          trackColor={{ false: theme.border, true: theme.primary }}
          onValueChange={onValueChange}
          pointerEvents="none"
          importantForAccessibility="no-hide-descendants"
          accessibilityElementsHidden
        />
      )}
    </>
  );

  if (busy) {
    return <View style={styles.menuRow}>{body}</View>;
  }

  return (
    <Pressable
      style={({ pressed }) => [styles.menuRow, pressed && styles.rowPressed]}
      accessibilityRole="switch"
      accessibilityLabel={title}
      accessibilityHint={subtitle}
      accessibilityState={{ checked: value, disabled: Boolean(disabled) }}
      disabled={disabled}
      onPress={() => onValueChange(!value)}
    >
      {body}
    </Pressable>
  );
}

export function ConnectedAppMark({
  name,
  color,
}: {
  name: IoniconName;
  color: string;
}) {
  return <Icon name={name} size={26} color={color} />;
}
