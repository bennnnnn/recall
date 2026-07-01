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

import { Theme } from "@/lib/theme";

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

export function SettingsLinkRow({
  title,
  value,
  onPress,
  styles,
  theme,
}: {
  title: string;
  value?: string;
  onPress: () => void;
  styles: SettingsStyles;
  theme: Theme;
}) {
  return (
    <Pressable style={styles.menuRow} onPress={onPress}>
      <Text style={[styles.rowTitle, styles.menuRowTitle]}>{title}</Text>
      <View style={styles.linkTrailing}>
        {value ? (
          <Text style={styles.linkValue} numberOfLines={1}>
            {value}
          </Text>
        ) : null}
        <Ionicons name="chevron-forward" size={18} color={theme.textTertiary} />
      </View>
    </Pressable>
  );
}

export function SettingsSwitchRow({
  title,
  value,
  disabled,
  onValueChange,
  styles,
  theme,
}: {
  title: string;
  value: boolean;
  disabled?: boolean;
  onValueChange: (next: boolean) => void;
  styles: SettingsStyles;
  theme: Theme;
}) {
  return (
    <View style={styles.menuRow}>
      <Text style={[styles.rowTitle, styles.menuRowTitle]}>{title}</Text>
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
  return (
    <View style={compact ? styles.menuRow : styles.row}>
      <Ionicons name={icon} size={19} color={theme.primary} />
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
  summary,
  expanded,
  busy,
  onToggle,
  children,
  styles,
  theme,
  showDivider = true,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  summary: string;
  expanded: boolean;
  busy: boolean;
  onToggle: () => void;
  children: ReactNode;
  styles: SettingsStyles;
  theme: Theme;
  showDivider?: boolean;
}) {
  return (
    <View style={showDivider ? styles.integrationPanel : styles.integrationPanelFirst}>
      <Pressable style={styles.integrationHeader} onPress={onToggle}>
        <Ionicons name={icon} size={19} color={theme.primary} />
        <View style={styles.rowBody}>
          <Text style={styles.rowTitle}>{title}</Text>
          <Text style={styles.meta} numberOfLines={1}>
            {summary}
          </Text>
        </View>
        {busy ? (
          <ActivityIndicator color={theme.primary} />
        ) : (
          <Ionicons
            name={expanded ? "chevron-up" : "chevron-down"}
            size={18}
            color={theme.textTertiary}
          />
        )}
      </Pressable>
      {expanded ? <View style={styles.integrationBody}>{children}</View> : null}
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
    <Pressable style={compact ? styles.menuRow : styles.row} onPress={onPress}>
      <Ionicons name={icon} size={19} color={danger ? theme.danger : theme.primary} />
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

    profileHeader: {
      alignItems: "center",
      gap: 4,
      marginBottom: 8,
      paddingTop: 8,
    },
    profileName: {
      fontSize: 20,
      fontWeight: "700",
      color: t.text,
      marginTop: 4,
    },
    profilePlan: {
      fontSize: 14,
      fontWeight: "600",
      color: t.textSecondary,
    },
    accountPro: { color: "#FF9F0A" },

    section: { marginTop: 20 },
    sectionLabel: {
      fontSize: 12,
      fontWeight: "700",
      color: t.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
      marginLeft: 4,
      marginBottom: 8,
    },
    sectionHint: { fontSize: 13, color: t.textSecondary, marginLeft: 4, marginBottom: 8 },
    group: {
      backgroundColor: t.surface,
      borderRadius: 16,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      padding: 14,
      gap: 10,
    },

    subLabel: { fontSize: 13, color: t.textSecondary, marginTop: 6 },
    chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
    chip: {
      borderRadius: 999,
      borderWidth: 1,
      borderColor: t.border,
      paddingHorizontal: 14,
      paddingVertical: 7,
      backgroundColor: t.bg,
    },
    chipActive: { backgroundColor: t.primary, borderColor: t.primary },
    chipText: { color: t.text, fontSize: 13, textTransform: "capitalize" },
    chipTextActive: { color: "#fff", fontSize: 13, fontWeight: "600", textTransform: "capitalize" },

    dropdown: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      backgroundColor: t.bg,
      borderRadius: 12,
      borderWidth: 1,
      borderColor: t.border,
      paddingHorizontal: 12,
      paddingVertical: 14,
    },
    dropdownText: { fontSize: 16, fontWeight: "600", color: t.text },

    pickerBackdrop: {
      flex: 1,
      backgroundColor: t.scrim,
      justifyContent: "flex-end",
    },
    pickerSheet: {
      backgroundColor: t.surface,
      borderTopLeftRadius: 20,
      borderTopRightRadius: 20,
      padding: 16,
      paddingBottom: 32,
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
      borderRadius: 12,
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
      minHeight: 48,
      paddingHorizontal: 14,
      paddingVertical: 12,
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
    meta: { fontSize: 13, color: t.textTertiary, marginTop: 1 },
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
      minHeight: 36,
    },
    integrationBody: {
      marginTop: 8,
      paddingLeft: 31,
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
      marginTop: 20,
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
      borderRadius: 16,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      overflow: "hidden",
    },
    menuStack: { gap: 12 },
    menuSeparator: {
      height: StyleSheet.hairlineWidth,
      backgroundColor: t.border,
      marginLeft: 43,
    },

    mOverlay: { flex: 1, backgroundColor: t.scrim, justifyContent: "center", padding: 24 },
    mSheet: { backgroundColor: t.bg, borderRadius: 20, padding: 20, gap: 14 },
    mTitle: { fontSize: 17, fontWeight: "700", color: t.text },
    mInput: {
      backgroundColor: t.surface,
      borderRadius: 12,
      padding: 12,
      fontSize: 16,
      color: t.text,
      borderWidth: 1.5,
      borderColor: t.primary,
    },
    mActions: { flexDirection: "row", gap: 10 },
    mCancel: {
      flex: 1,
      borderRadius: 12,
      borderWidth: 1,
      borderColor: t.border,
      padding: 12,
      alignItems: "center",
    },
    mCancelText: { fontSize: 15, color: t.textSecondary, fontWeight: "600" },
    mSave: { flex: 1, borderRadius: 12, backgroundColor: t.primary, padding: 12, alignItems: "center" },
    mSaveText: { fontSize: 15, color: "#fff", fontWeight: "700" },
  });
}
