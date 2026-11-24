/**
 * The plans page's parts: the plan as one card (its name, what it gives),
 * what is paid today and next, and the links a store asks of a subscription page.
 */
import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";
import type { TimelineRow } from "@/features/billing/model/planCopy";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { getLegalPrivacyUrl, getLegalTermsUrl } from "@/lib/legalUrls";
import { openAllowedUrl } from "@/lib/linkSchemePolicy";
import { Theme, useTheme, withAlpha } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";

/** The plan: its name and what it gives, in two columns of short lines. What it costs is the
 * dates row's. */
export function PlanCard({ title, features }: { title: string; features: readonly string[] }) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <View style={s.card} testID="upgrade-plan-card">
      <Text style={s.cardTitle}>{title}</Text>
      <View style={s.cardList}>
        {features.map((feature) => (
          <View key={feature} style={s.cardItem}>
            <Icon name="check" size={IconSize.xs} color={theme.primary} />
            <Text style={s.cardBody}>{feature}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}


/** What is paid when: today (nothing, in a free trial) and the next payment's day. */
export function PlanTimeline({ rows }: { rows: readonly [TimelineRow, TimelineRow] }) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <View style={s.timeline} testID="upgrade-timeline">
      <View style={s.rail} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        <View style={s.dot} />
        <View style={s.line} />
        <View style={s.dot} />
      </View>
      <View style={s.timelineRows}>
        {rows.map((row, index) => (
          <View key={row.label} style={s.timelineRow}>
            <Text style={[s.timelineLabel, index === 0 && s.timelineLabelFirst]} numberOfLines={2}>
              {row.label}
            </Text>
            {row.chip ? (
              <View style={s.chip}>
                <Text style={s.chipText}>{row.chip}</Text>
              </View>
            ) : null}
            <Text style={[s.amount, index === 0 && s.amountFirst]}>{row.amount}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

/** A small link is about 17pt tall: this makes it a 45pt target. */
const SMALL_LINK_SLOP = { top: 14, bottom: 14, left: Space.xs, right: Space.xs };

/** Privacy, Terms and (when the build can sell) Restore, over the renewal terms in the
 * smallest type: what a store asks of a subscription page. */
export function PlansSmallPrint({
  renews,
  links,
  restore,
}: {
  renews: string;
  links: { terms: string; privacy: string };
  restore?: { label: string; onPress: () => void; disabled: boolean };
}) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const items = [
    { label: links.privacy, onPress: () => void openAllowedUrl(getLegalPrivacyUrl()), disabled: false, role: "link" as const },
    { label: links.terms, onPress: () => void openAllowedUrl(getLegalTermsUrl()), disabled: false, role: "link" as const },
    ...(restore ? [{ ...restore, role: "button" as const }] : []),
  ];
  return (
    <View style={s.small}>
      <View style={s.smallLinks}>
        {items.map((item, index) => (
          <View key={item.label} style={s.smallLinkRow}>
            {index > 0 ? (
              <Text style={s.smallDivider} accessibilityElementsHidden importantForAccessibility="no">
                |
              </Text>
            ) : null}
            <Pressable
              onPress={item.onPress}
              disabled={item.disabled}
              accessibilityRole={item.role}
              accessibilityLabel={item.label}
              hitSlop={SMALL_LINK_SLOP}
            >
              <Text style={s.smallLink}>{item.label}</Text>
            </Pressable>
          </View>
        ))}
      </View>
      <Text style={s.smallText}>{renews}</Text>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    card: {
      borderRadius: Radius.xl,
      // White on the page's tint (the dark theme's raised surface there), so it reads as one card.
      backgroundColor: theme.isDark ? theme.surface : theme.elevated,
      borderWidth: 1,
      borderColor: theme.border,
      paddingHorizontal: Space.lg,
      paddingVertical: Space.md,
      gap: Space.sm,
    },
    cardTitle: { ...Type.title, ...Weight.bold, color: theme.text },
    cardList: { flexDirection: "row", flexWrap: "wrap", rowGap: Space.xs },
    cardItem: { width: "50%", flexDirection: "row", alignItems: "center", gap: Space.xs, paddingRight: Space.xs },
    cardBody: { flex: 1, ...Type.body, color: theme.textSecondary },
    timeline: { flexDirection: "row", gap: Space.md, paddingHorizontal: Space.xxs },
    rail: { alignItems: "center", paddingVertical: Space.xs },
    dot: { width: 9, height: 9, borderRadius: Radius.full, backgroundColor: theme.text },
    line: { flex: 1, width: 2, backgroundColor: theme.text, marginVertical: 2 },
    timelineRows: { flex: 1, gap: Space.sm },
    timelineRow: { flexDirection: "row", alignItems: "center", gap: Space.sm },
    timelineLabel: { flex: 1, ...Type.body, color: theme.textSecondary },
    timelineLabelFirst: { ...Weight.semibold, color: theme.text },
    chip: {
      borderRadius: Radius.full,
      backgroundColor: withAlpha(theme.primary, theme.isDark ? 0.24 : 0.12),
      paddingHorizontal: Space.sm,
      paddingVertical: Space.xxs,
    },
    chipText: { ...Type.caption, ...Weight.semibold, color: theme.primary },
    amount: { ...Type.body, color: theme.textSecondary, fontVariant: ["tabular-nums"] },
    amountFirst: { ...Weight.bold, color: theme.text },
    small: { gap: Space.sm, alignItems: "center" },
    smallText: { ...Type.caption, ...Weight.regular, color: theme.textTertiary, textAlign: "center" },
    smallLinks: { flexDirection: "row", flexWrap: "wrap", justifyContent: "center" },
    smallLinkRow: { flexDirection: "row", alignItems: "center", gap: Space.md, marginHorizontal: Space.sm },
    smallDivider: { ...Type.caption, color: theme.textTertiary },
    smallLink: { ...Type.caption, ...Weight.semibold, color: theme.textSecondary },
  });
}
