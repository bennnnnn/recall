import { ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
import { Icon } from "@/components/Icon";
import { type IoniconName } from "@/lib/icons";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, withAlpha } from "@/lib/theme";
import { Type } from "@/lib/type";

export type SettingsStyles = ReturnType<typeof makeSettingsStyles>;

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
  title: string;
  subtitle?: string;
  value?: string;
  chevron?: "forward" | "down" | "up";
  busy?: boolean;
  danger?: boolean;
  styles: SettingsStyles;
  theme: Theme;
}) {
  return (
    <>
      {icon ? (
        <Icon name={icon} danger={danger} />
      ) : null}
      <View style={styles.rowBody}>
        <Text style={[styles.rowTitle, danger && { color: theme.danger }]}>
          {title}
        </Text>
        {subtitle ? <Text style={styles.meta}>{subtitle}</Text> : null}
      </View>
      <View style={styles.linkTrailing}>
        {value ? (
          <Text style={styles.linkValue} numberOfLines={1}>
            {value}
          </Text>
        ) : null}
        {busy ? (
          <ActivityIndicator size="small" color={theme.primary} />
        ) : chevron ? (
          <Icon name={`chevron-${chevron}`} size={18} color={theme.textTertiary} />
        ) : null}
      </View>
    </>
  );
}

export function SettingsLinkRow({
  title,
  subtitle,
  value,
  icon,
  danger,
  onPress,
  styles,
  theme,
}: {
  title: string;
  subtitle?: string;
  value?: string;
  icon?: IoniconName;
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
        title={title}
        subtitle={subtitle}
        value={value}
        chevron={danger ? undefined : "forward"}
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
  styles,
  theme,
}: {
  title: string;
  subtitle?: string;
  value?: string;
  icon?: IoniconName;
  styles: SettingsStyles;
  theme: Theme;
}) {
  return (
    <View style={styles.menuRow} accessibilityRole="text">
      <SettingsRowChrome
        icon={icon}
        title={title}
        subtitle={subtitle}
        value={value}
        styles={styles}
        theme={theme}
      />
    </View>
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
          chevron={expanded ? "up" : "down"}
          busy={busy}
          styles={styles}
          theme={theme}
        />
      </Pressable>
      {expanded ? (
        <View style={styles.inlineOptionWell}>
          {options.map((option) => {
            const active = option.key === selectedKey;
            return (
              <Pressable
                key={option.key}
                style={({ pressed }) => [
                  styles.inlineOption,
                  active && styles.inlineOptionActive,
                  pressed && styles.rowPressed,
                ]}
                disabled={disabled}
                accessibilityRole="radio"
                accessibilityState={{ selected: active }}
                accessibilityLabel={option.label}
                onPress={() => {
                  if (!active) onSelect(option.key);
                  onToggle();
                }}
              >
                <Text
                  style={[
                    styles.inlineOptionText,
                    active && styles.inlineOptionTextActive,
                  ]}
                >
                  {option.label}
                </Text>
                {active ? (
                  <Icon name="checkmark" size={18} color={theme.primary} />
                ) : null}
              </Pressable>
            );
          })}
        </View>
      ) : null}
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
      {icon ? <Icon name={icon} /> : null}
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
      style={styles.menuRow}
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

export function IntegrationPanel({
  icon,
  title,
  subtitle,
  summary,
  busy,
  children,
  styles,
  theme,
  showDivider = true,
}: {
  icon: IoniconName;
  title: string;
  subtitle?: string;
  summary: string;
  busy: boolean;
  children: ReactNode;
  styles: SettingsStyles;
  theme: Theme;
  showDivider?: boolean;
}) {
  return (
    <View style={showDivider ? styles.integrationPanel : styles.integrationPanelFirst}>
      <View style={styles.integrationHeader}>
        <Icon name={icon} />
        <View style={styles.rowBody}>
          <Text style={styles.rowTitle}>{title}</Text>
          {subtitle ? <Text style={styles.meta}>{subtitle}</Text> : null}
        </View>
        <View style={styles.linkTrailing}>
          <Text style={styles.linkValue} numberOfLines={1}>
            {summary}
          </Text>
          {busy ? <ActivityIndicator color={theme.primary} /> : null}
        </View>
      </View>
      <View style={styles.integrationBody}>{children}</View>
    </View>
  );
}

export function makeSettingsStyles(t: Theme) {
  return StyleSheet.create({
    center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: t.bg },
    root: { flex: 1, backgroundColor: t.bg },
    scroll: { flex: 1 },
    content: { padding: Space.md, paddingBottom: Space.xl + Space.xs },

    stickyProfile: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.border,
      backgroundColor: t.bg,
    },
    stickyName: {
      flex: 1,
      ...Type.body,
      fontWeight: "700",
      color: t.text,
    },
    stickyAccount: {
      ...Type.caption,
      fontWeight: "700",
      color: t.textSecondary,
    },

    rowPressed: { opacity: 0.55 },

    profileHeader: {
      width: "100%",
      alignItems: "center",
      gap: Space.xs,
      marginBottom: Space.sm,
      paddingTop: Space.sm,
      paddingBottom: Space.sm,
    },
    profileAvatarWrap: {
      width: 80,
      height: 80,
      borderRadius: 40,
      overflow: "hidden",
      alignItems: "center",
      justifyContent: "center",
      alignSelf: "center",
      backgroundColor: t.surfaceAlt,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
    },
    profileEmail: {
      ...Type.secondary,
      color: t.textSecondary,
    },
    profilePlan: {
      ...Type.label,
      color: t.textSecondary,
    },
    planPill: {
      marginTop: Space.xxs,
      paddingHorizontal: 10,
      paddingVertical: Space.xxs,
      borderRadius: Radius.full,
      backgroundColor: t.primaryLight,
    },
    planPillPro: {
      backgroundColor: withAlpha(t.warning, 0.16),
    },
    planPillText: {
      ...Type.caption,
      fontWeight: "700",
      color: t.primary,
    },
    planPillTextPro: { color: t.warning },
    accountPro: { color: t.warning },
    section: { marginTop: Space.lg },
    sectionLabel: {
      ...Type.caption,
      fontWeight: "700",
      color: t.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
      marginLeft: Space.xxs,
      marginBottom: Space.xs,
    },
    sectionHint: {
      ...Type.caption,
      fontWeight: "400",
      color: t.textSecondary,
      marginLeft: Space.xxs,
      marginBottom: Space.xs,
    },
    group: {
      backgroundColor: t.surfaceAlt,
      borderRadius: Radius.lg,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      padding: Space.sm,
      gap: Space.xs,
    },

    subLabel: { ...Type.caption, fontWeight: "400", color: t.textSecondary, marginTop: Space.xs },

    dropdown: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      backgroundColor: t.bg,
      borderRadius: Radius.md,
      borderWidth: 1,
      borderColor: t.border,
      paddingHorizontal: Space.sm,
      paddingVertical: 14,
    },
    dropdownText: { ...Type.body, fontWeight: "600", color: t.text },

    pickerSheet: {
      backgroundColor: t.surface,
      borderTopLeftRadius: 20,
      borderTopRightRadius: 20,
      paddingHorizontal: Space.md,
      paddingTop: Space.md,
      gap: Space.xxs,
    },
    pickerTitle: {
      ...Type.caption,
      fontWeight: "700",
      color: t.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
      marginBottom: Space.xs,
    },
    inlineOptionWell: {
      marginHorizontal: 14,
      marginBottom: Space.sm,
      backgroundColor: t.bg,
      borderRadius: Radius.md,
      overflow: "hidden",
    },
    inlineOption: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: Space.sm,
      minHeight: 44,
      paddingVertical: 10,
      paddingHorizontal: Space.sm,
    },
    inlineOptionActive: { backgroundColor: t.primaryLight },
    inlineOptionText: {
      flex: 1,
      ...Type.secondary,
      fontWeight: "500",
      color: t.text,
    },
    inlineOptionTextActive: {
      fontWeight: "600",
      color: t.primary,
    },
    pickerOption: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      paddingVertical: 14,
      paddingHorizontal: Space.xs,
      borderRadius: Radius.md,
    },
    pickerOptionActive: { backgroundColor: t.primaryLight },
    pickerOptionMain: { flex: 1, gap: 2 },
    pickerOptionMeta: { ...Type.caption, fontWeight: "400", color: t.textSecondary, lineHeight: 18 },
    pickerOptionText: { flex: 1, ...Type.body, fontWeight: "600", color: t.text },
    pickerOptionTextActive: { color: t.primary },
    pickerOptionDisabled: { opacity: 0.45 },
    pickerSheetScroll: { maxHeight: "70%" },

    menuRow: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: Space.sm,
      minHeight: 52,
      paddingHorizontal: 14,
      paddingVertical: 13,
    },
    linkTrailing: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
      flexShrink: 1,
      maxWidth: "55%",
    },
    linkValue: {
      ...Type.secondary,
      color: t.textTertiary,
    },
    rowBody: { flex: 1 },
    rowTitle: { ...Type.secondary, fontWeight: "600", color: t.text },
    meta: {
      ...Type.caption,
      fontWeight: "400",
      color: t.textTertiary,
      marginTop: 1,
    },
    linkBtn: {
      minHeight: 44,
      justifyContent: "center",
      paddingHorizontal: Space.xxs,
      paddingVertical: Space.xs,
    },
    rowActions: { alignItems: "flex-end", gap: 2 },
    linkBtnText: { ...Type.secondary, fontWeight: "600", color: t.primary },
    linkBtnDanger: { ...Type.secondary, fontWeight: "600", color: t.danger },

    integrationPanel: {
      paddingTop: 10,
      marginTop: 6,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: t.border,
    },
    integrationPanelFirst: {
      paddingTop: 2,
    },
    integrationHeader: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      minHeight: 52,
      paddingHorizontal: 14,
      paddingVertical: 13,
    },
    integrationBody: {
      marginTop: Space.xxs,
      paddingLeft: 46,
      paddingRight: 14,
      paddingBottom: Space.sm,
      gap: Space.xs,
    },
    integrationActions: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "flex-end",
    },

    signOut: {
      marginTop: Space.lg,
    },
    signOutRow: {
      paddingVertical: Space.md,
      alignItems: "center",
    },
    signOutText: { ...Type.secondary, color: t.danger, fontWeight: "700" },

    footerBand: {
      marginTop: Space.lg,
      marginHorizontal: -Space.md,
      paddingHorizontal: Space.md,
      paddingTop: Space.md,
      paddingBottom: Space.xs,
      backgroundColor: t.surfaceAlt,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: t.border,
    },
    footerGroup: {
      backgroundColor: t.surfaceAlt,
      borderRadius: Radius.xl,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      overflow: "hidden",
    },
    menuStack: { gap: Space.sm },
    menuSeparator: {
      height: StyleSheet.hairlineWidth,
      backgroundColor: t.border,
      marginLeft: 14,
    },
    menuSeparatorWithIcon: {
      marginLeft: 46,
    },

    mKeyboardAvoider: { flex: 1 },
    mOverlay: { flex: 1, backgroundColor: t.scrim, justifyContent: "center", padding: Space.lg },
    mSheet: { backgroundColor: t.bg, borderRadius: Radius.sheet, padding: 20, gap: 14 },
    mTitle: { ...Type.navTitle, color: t.text },
    mInput: {
      backgroundColor: t.surface,
      borderRadius: Radius.md,
      padding: Space.sm,
      ...Type.body,
      color: t.text,
      borderWidth: 1.5,
      borderColor: t.primary,
    },
    mActions: { flexDirection: "row", gap: Space.xs },
    mActionBtn: { flex: 1 },
  });
}
