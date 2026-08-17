import { ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, withAlpha } from "@/lib/theme";
import { Type } from "@/lib/type";

export type SettingsIconTone = "primary" | "accent" | "success" | "warning";

function iconToneColors(theme: Theme, tone: SettingsIconTone) {
  switch (tone) {
    case "accent":
      return { fg: theme.accent, bg: theme.accentLight };
    case "success":
      return { fg: theme.success, bg: theme.successLight };
    case "warning":
      return { fg: theme.warning, bg: withAlpha(theme.warning, 0.16) };
    default:
      return { fg: theme.primary, bg: theme.primaryLight };
  }
}

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
  iconTone = "primary",
  title,
  subtitle,
  value,
  showChevron,
  danger,
  styles,
  theme,
}: {
  icon?: keyof typeof Ionicons.glyphMap;
  iconTone?: SettingsIconTone;
  title: string;
  subtitle?: string;
  value?: string;
  showChevron: boolean;
  danger?: boolean;
  styles: SettingsStyles;
  theme: Theme;
}) {
  const tone = danger
    ? { fg: theme.danger, bg: theme.dangerLight }
    : iconToneColors(theme, iconTone);
  return (
    <>
      {icon ? (
        <View style={[styles.iconWell, { backgroundColor: tone.bg }]}>
          <Ionicons name={icon} size={18} color={tone.fg} />
        </View>
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
        {showChevron ? (
          <Ionicons name="chevron-forward" size={18} color={theme.textTertiary} />
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
  iconTone,
  danger,
  onPress,
  styles,
  theme,
}: {
  title: string;
  subtitle?: string;
  value?: string;
  icon?: keyof typeof Ionicons.glyphMap;
  iconTone?: SettingsIconTone;
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
        iconTone={iconTone}
        title={title}
        subtitle={subtitle}
        value={value}
        showChevron={!danger}
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
  iconTone,
  styles,
  theme,
}: {
  title: string;
  subtitle?: string;
  value?: string;
  icon?: keyof typeof Ionicons.glyphMap;
  iconTone?: SettingsIconTone;
  styles: SettingsStyles;
  theme: Theme;
}) {
  return (
    <View style={styles.menuRow} accessibilityRole="text">
      <SettingsRowChrome
        icon={icon}
        iconTone={iconTone}
        title={title}
        subtitle={subtitle}
        value={value}
        showChevron={false}
        styles={styles}
        theme={theme}
      />
    </View>
  );
}

export function SettingsSwitchRow({
  title,
  subtitle,
  icon,
  iconTone,
  value,
  disabled,
  onValueChange,
  styles,
  theme,
}: {
  title: string;
  subtitle?: string;
  icon?: keyof typeof Ionicons.glyphMap;
  iconTone?: SettingsIconTone;
  value: boolean;
  disabled?: boolean;
  onValueChange: (next: boolean) => void;
  styles: SettingsStyles;
  theme: Theme;
}) {
  const tone = iconToneColors(theme, iconTone ?? "primary");
  return (
    <View style={styles.menuRow}>
      {icon ? (
        <View style={[styles.iconWell, { backgroundColor: tone.bg }]}>
          <Ionicons name={icon} size={18} color={tone.fg} />
        </View>
      ) : null}
      <View style={styles.rowBody}>
        <Text style={styles.rowTitle}>{title}</Text>
        {subtitle ? <Text style={styles.meta}>{subtitle}</Text> : null}
      </View>
      <Switch
        value={value}
        disabled={disabled}
        thumbColor={theme.bg}
        trackColor={{ false: theme.border, true: theme.primary }}
        onValueChange={onValueChange}
      />
    </View>
  );
}

export function Section({
  label,
  hint,
  children,
  styles,
}: {
  label?: string;
  hint?: string;
  children: ReactNode;
  styles: SettingsStyles;
}) {
  return (
    <View style={styles.section}>
      {label ? <Text style={styles.sectionLabel}>{label}</Text> : null}
      {hint ? <Text style={styles.sectionHint}>{hint}</Text> : null}
      <View style={styles.group}>{children}</View>
    </View>
  );
}

export function InfoRow({
  icon,
  title,
  value,
  compact,
  styles,
  theme,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  value: string;
  compact?: boolean;
  styles: SettingsStyles;
  theme: Theme;
}) {
  const tone = iconToneColors(theme, "primary");
  return (
    <View style={compact ? styles.menuRow : styles.row}>
      <View style={[styles.iconWell, { backgroundColor: tone.bg }]}>
        <Ionicons name={icon} size={18} color={tone.fg} />
      </View>
      <View style={styles.rowBody}>
        <Text style={styles.rowTitle}>{title}</Text>
        <Text style={styles.meta}>{value}</Text>
      </View>
    </View>
  );
}

export function Chip({
  label,
  active,
  disabled,
  onPress,
  styles,
}: {
  label: string;
  active: boolean;
  disabled?: boolean;
  onPress: () => void;
  styles: SettingsStyles;
}) {
  return (
    <Pressable
      disabled={disabled}
      style={[styles.chip, active && styles.chipActive]}
      onPress={onPress}
    >
      <Text style={active ? styles.chipTextActive : styles.chipText}>{label}</Text>
    </Pressable>
  );
}

export function IntegrationPanel({
  icon,
  title,
  subtitle,
  summary,
  expanded,
  busy,
  onToggle,
  children,
  styles,
  theme,
  showDivider = true,
  /** When false, body is always visible (no accordion chrome). */
  collapsible = true,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  subtitle?: string;
  summary: string;
  expanded: boolean;
  busy: boolean;
  onToggle: () => void;
  children: ReactNode;
  styles: SettingsStyles;
  theme: Theme;
  showDivider?: boolean;
  collapsible?: boolean;
}) {
  const showBody = !collapsible || expanded;
  const tone = iconToneColors(theme, "primary");
  const header = (
    <>
      <View style={[styles.iconWell, { backgroundColor: tone.bg }]}>
        <Ionicons name={icon} size={18} color={tone.fg} />
      </View>
      <View style={styles.rowBody}>
        <Text style={styles.rowTitle}>{title}</Text>
        {subtitle ? <Text style={styles.meta}>{subtitle}</Text> : null}
      </View>
      <View style={styles.linkTrailing}>
        <Text style={styles.linkValue} numberOfLines={1}>
          {summary}
        </Text>
        {busy ? (
          <ActivityIndicator color={theme.primary} />
        ) : collapsible ? (
          <Ionicons
            name={expanded ? "chevron-up" : "chevron-down"}
            size={18}
            color={theme.textTertiary}
          />
        ) : null}
      </View>
    </>
  );
  return (
    <View style={showDivider ? styles.integrationPanel : styles.integrationPanelFirst}>
      {collapsible ? (
        <Pressable
          style={({ pressed }) => [styles.integrationHeader, pressed && styles.rowPressed]}
          onPress={onToggle}
          accessibilityRole="button"
        >
          {header}
        </Pressable>
      ) : (
        <View style={styles.integrationHeader}>{header}</View>
      )}
      {showBody ? <View style={styles.integrationBody}>{children}</View> : null}
    </View>
  );
}

export function AccordionSection({
  label,
  icon,
  count,
  expanded,
  onToggle,
  emptyText,
  viewAllLabel,
  onViewAll,
  children,
  styles,
  theme,
}: {
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  count: number;
  expanded: boolean;
  onToggle: () => void;
  emptyText: string;
  viewAllLabel: string;
  onViewAll: () => void;
  children: ReactNode;
  styles: SettingsStyles;
  theme: Theme;
}) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionLabel}>{label}</Text>
      <View style={styles.group}>
        <Pressable style={styles.accordionHeader} onPress={onToggle}>
          <Ionicons name={icon} size={19} color={theme.primary} />
          <View style={styles.rowBody}>
            <Text style={styles.meta}>
              {count > 0 ? String(count) : emptyText}
            </Text>
          </View>
          <Ionicons
            name={expanded ? "chevron-up" : "chevron-down"}
            size={18}
            color={theme.textTertiary}
          />
        </Pressable>

        {expanded ? (
          <View style={styles.accordionBody}>
            {count === 0 ? (
              <Text style={styles.accordionEmpty}>{emptyText}</Text>
            ) : (
              children
            )}
            <Pressable style={styles.viewAllRow} onPress={onViewAll}>
              <Text style={styles.viewAllText}>{viewAllLabel}</Text>
              <Ionicons name="chevron-forward" size={16} color={theme.textTertiary} />
            </Pressable>
          </View>
        ) : null}
      </View>
    </View>
  );
}

export function ItemRow({
  title,
  meta,
  onPress,
  styles,
  theme,
}: {
  title: string;
  meta?: string;
  onPress: () => void;
  styles: SettingsStyles;
  theme: Theme;
}) {
  return (
    <Pressable style={styles.itemRow} onPress={onPress}>
      <View style={styles.rowBody}>
        <Text style={styles.itemTitle} numberOfLines={1}>
          {title}
        </Text>
        {meta ? (
          <Text style={styles.meta} numberOfLines={1}>
            {meta}
          </Text>
        ) : null}
      </View>
      <Ionicons name="chevron-forward" size={16} color={theme.textTertiary} />
    </Pressable>
  );
}

export function NavRow({
  icon,
  title,
  meta,
  onPress,
  danger,
  compact,
  styles,
  theme,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  meta?: string;
  onPress: () => void;
  danger?: boolean;
  /** Tighter padding for footer menu rows. */
  compact?: boolean;
  styles: SettingsStyles;
  theme: Theme;
}) {
  return (
    <Pressable
      style={({ pressed }) => [
        compact ? styles.menuRow : styles.row,
        pressed && styles.rowPressed,
      ]}
      onPress={onPress}
      accessibilityRole="button"
    >
      <View
        style={[
          styles.iconWell,
          { backgroundColor: danger ? theme.dangerLight : theme.primaryLight },
        ]}
      >
        <Ionicons
          name={icon}
          size={18}
          color={danger ? theme.danger : theme.primary}
        />
      </View>
      <View style={styles.rowBody}>
        <Text style={[styles.rowTitle, danger && { color: theme.danger }]}>{title}</Text>
        {meta ? <Text style={styles.meta}>{meta}</Text> : null}
      </View>
      {!danger ? (
        <Ionicons name="chevron-forward" size={18} color={theme.textTertiary} />
      ) : null}
    </Pressable>
  );
}

export function makeSettingsStyles(t: Theme) {
  return StyleSheet.create({
    center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: t.bg },
    root: { flex: 1, backgroundColor: t.bg },
    scroll: { flex: 1 },
    content: { padding: 16, paddingBottom: 40 },

    stickyProfile: {
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      paddingHorizontal: 16,
      paddingVertical: 10,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.border,
      backgroundColor: t.bg,
    },
    stickyName: {
      flex: 1,
      fontSize: 16,
      fontWeight: "700",
      color: t.text,
    },
    stickyAccount: {
      fontSize: 13,
      fontWeight: "700",
      color: t.textSecondary,
    },

    rowPressed: { opacity: 0.55 },

    profileHeader: {
      alignItems: "center",
      gap: 6,
      marginBottom: 4,
      paddingTop: 12,
      paddingBottom: 4,
    },
    profileName: {
      fontSize: 22,
      fontWeight: "700",
      color: t.text,
      marginTop: 6,
    },
    profileEmail: {
      ...Type.secondary,
      color: t.textSecondary,
    },
    profilePlan: {
      fontSize: 14,
      fontWeight: "600",
      color: t.textSecondary,
    },
    planPill: {
      marginTop: 4,
      paddingHorizontal: 10,
      paddingVertical: 4,
      borderRadius: Radius.full,
      backgroundColor: t.primaryLight,
    },
    planPillPro: {
      backgroundColor: withAlpha(t.warning, 0.16),
    },
    planPillText: {
      fontSize: 13,
      fontWeight: "700",
      color: t.primary,
    },
    planPillTextPro: { color: t.warning },
    accountPro: { color: t.warning },
    iconWell: {
      width: 32,
      height: 32,
      borderRadius: Radius.xs,
      alignItems: "center",
      justifyContent: "center",
    },

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
      backgroundColor: t.surface,
      borderRadius: Radius.xl,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      padding: Space.sm,
      gap: Space.xs,
    },

    subLabel: { fontSize: 13, color: t.textSecondary, marginTop: 6 },
    chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
    chip: {
      borderRadius: Radius.full,
      borderWidth: 1,
      borderColor: t.border,
      paddingHorizontal: 14,
      paddingVertical: 7,
      backgroundColor: t.bg,
    },
    chipActive: { backgroundColor: t.primary, borderColor: t.primary },
    chipText: { color: t.text, fontSize: 13, textTransform: "capitalize" },
    chipTextActive: { color: t.onPrimary, fontSize: 13, fontWeight: "600", textTransform: "capitalize" },

    dropdown: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      backgroundColor: t.bg,
      borderRadius: Radius.md,
      borderWidth: 1,
      borderColor: t.border,
      paddingHorizontal: 12,
      paddingVertical: 14,
    },
    dropdownText: { fontSize: 16, fontWeight: "600", color: t.text },

    pickerSheet: {
      backgroundColor: t.surface,
      borderTopLeftRadius: 20,
      borderTopRightRadius: 20,
      paddingHorizontal: 16,
      paddingTop: 16,
      gap: 4,
    },
    pickerTitle: {
      fontSize: 13,
      fontWeight: "700",
      color: t.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
      marginBottom: 8,
    },
    pickerOption: {
      flexDirection: "row",
      alignItems: "center",
      gap: 12,
      paddingVertical: 14,
      paddingHorizontal: 8,
      borderRadius: Radius.md,
    },
    pickerOptionActive: { backgroundColor: t.primaryLight },
    pickerOptionMain: { flex: 1, gap: 2 },
    pickerOptionMeta: { fontSize: 13, color: t.textSecondary, lineHeight: 18 },
    pickerOptionText: { flex: 1, fontSize: 16, fontWeight: "600", color: t.text },
    pickerOptionTextActive: { color: t.primary },
    pickerOptionDisabled: { opacity: 0.45 },
    pickerSheetScroll: { maxHeight: "70%" },

    row: { flexDirection: "row", alignItems: "center", gap: 12, minHeight: 32 },
    menuRow: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 12,
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
      fontSize: 15,
      color: t.textTertiary,
    },
    rowBody: { flex: 1 },
    rowTitle: { fontSize: 15, fontWeight: "600", color: t.text },
    menuRowTitle: { flex: 1 },
    meta: {
      ...Type.caption,
      fontWeight: "400",
      color: t.textTertiary,
      marginTop: 1,
    },
    linkBtn: { paddingHorizontal: 4, paddingVertical: 6 },
    rowActions: { alignItems: "flex-end", gap: 2 },
    linkBtnText: { fontSize: 15, fontWeight: "600", color: t.primary },
    linkBtnDanger: { fontSize: 15, fontWeight: "600", color: t.danger },

    accordionHeader: {
      flexDirection: "row",
      alignItems: "center",
      gap: 12,
      minHeight: 36,
    },
    accordionBody: {
      marginTop: 8,
      paddingTop: 8,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: t.border,
      gap: 2,
    },
    accordionEmpty: {
      fontSize: 14,
      color: t.textSecondary,
      paddingVertical: 6,
    },
    accordionHint: {
      fontSize: 13,
      color: t.textSecondary,
      lineHeight: 18,
      marginBottom: 4,
    },
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
      gap: 12,
      minHeight: 52,
      paddingHorizontal: 14,
      paddingVertical: 13,
    },
    integrationBody: {
      marginTop: 4,
      paddingLeft: 58,
      paddingRight: 14,
      paddingBottom: 12,
      gap: 8,
    },
    integrationActions: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "flex-end",
    },
    itemRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      paddingVertical: 8,
      paddingHorizontal: 2,
    },
    itemTitle: { fontSize: 15, fontWeight: "500", color: t.text },
    viewAllRow: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingTop: 8,
      marginTop: 4,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: t.border,
    },
    viewAllText: { fontSize: 14, fontWeight: "600", color: t.primary },

    bar: { height: 6, borderRadius: 3, backgroundColor: t.bg, overflow: "hidden" },
    barFill: { height: 6, borderRadius: 3, backgroundColor: t.primary },

    signOut: {
      marginTop: Space.lg,
    },
    signOutRow: {
      paddingVertical: 16,
      alignItems: "center",
    },
    signOutText: { color: t.danger, fontWeight: "700", fontSize: 15 },

    footerBand: {
      marginTop: 24,
      marginHorizontal: -16,
      paddingHorizontal: 16,
      paddingTop: 16,
      paddingBottom: 8,
      backgroundColor: t.surfaceAlt,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: t.border,
    },
    footerGroup: {
      backgroundColor: t.surface,
      borderRadius: Radius.xl,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      overflow: "hidden",
    },
    menuStack: { gap: 12 },
    menuSeparator: {
      height: StyleSheet.hairlineWidth,
      backgroundColor: t.border,
      marginLeft: 14,
    },
    menuSeparatorWithIcon: {
      marginLeft: 58,
    },

    mKeyboardAvoider: { flex: 1 },
    mOverlay: { flex: 1, backgroundColor: t.scrim, justifyContent: "center", padding: 24 },
    mSheet: { backgroundColor: t.bg, borderRadius: Radius.sheet, padding: 20, gap: 14 },
    mTitle: { fontSize: 17, fontWeight: "700", color: t.text },
    mInput: {
      backgroundColor: t.surface,
      borderRadius: Radius.md,
      padding: 12,
      fontSize: 16,
      color: t.text,
      borderWidth: 1.5,
      borderColor: t.primary,
    },
    mActions: { flexDirection: "row", gap: Space.xs },
    mActionBtn: { flex: 1 },
  });
}
