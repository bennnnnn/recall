/**
 * The plans page's parts: the plan as one card (its name, what it gives),
 * what is paid today and next, and the links a store asks of a subscription page.
 */
import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from "react-native";

import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";
import type { TimelineRow } from "@/features/billing/model/planCopy";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { getLegalPrivacyUrl, getLegalTermsUrl } from "@/lib/legalUrls";
import { openAllowedUrl } from "@/lib/linkSchemePolicy";
import { Theme, useTheme, withAlpha } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";

/** The page's text grows with the phone's text size up to this, so it still fits one screen. */
export const PLANS_FONT_SCALE = 1.3;

/** About how wide one character of the list's text is at the phone's normal text size. */
const CHAR_WIDTH = 8.5;
/** A line's check mark and the gap after it. */
const MARK_WIDTH = IconSize.xs + Space.xs;

/**
 * Two columns only when the longest line fits half the card whole: on a narrow phone, or in a
 * language with long words, one column, so no word ever breaks.
 */
export function benefitColumns(listWidth: number, features: readonly string[], fontScale = 1): 1 | 2 {
  const longest = Math.max(0, ...features.map((feature) => feature.length));
  const scale = Math.min(fontScale, PLANS_FONT_SCALE);
  return listWidth / 2 >= longest * CHAR_WIDTH * scale + MARK_WIDTH + Space.xs ? 2 : 1;
}

/** The lines the card shows; "See all Pro benefits" opens every one below itself. */
const FIRST_BENEFITS = 2;

/** Benefit lines, one per row, or two side by side where every line fits whole. */
function BenefitLines({ features, testID }: { features: readonly string[]; testID: string }) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [width, setWidth] = useState(0);
  const { fontScale } = useWindowDimensions();
  const columns = benefitColumns(width, features, fontScale);
  return (
    <View style={s.cardList} onLayout={(event) => setWidth(event.nativeEvent.layout.width)} testID={testID}>
      {features.map((feature) => (
        <View key={feature} style={[s.cardItem, columns === 2 && s.cardItemHalf]}>
          <Icon name="check" size={IconSize.xs} color={theme.primary} />
          <Text style={s.cardBody} numberOfLines={1} maxFontSizeMultiplier={PLANS_FONT_SCALE}>
            {feature}
          </Text>
        </View>
      ))}
    </View>
  );
}

/** The plan: its name and its first two benefits. The rest open under "See all Pro benefits". */
export function PlanCard({ title, features }: { title: string; features: readonly string[] }) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <View style={s.card} testID="upgrade-plan-card">
      <Text style={s.cardTitle} maxFontSizeMultiplier={PLANS_FONT_SCALE}>
        {title}
      </Text>
      <BenefitLines features={features.slice(0, FIRST_BENEFITS)} testID="upgrade-benefits" />
    </View>
  );
}

/** Every benefit, opened under the link that asked for it. */
export function AllBenefits({ features }: { features: readonly string[] }) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <View style={s.allBenefits} testID="upgrade-all-benefits">
      <BenefitLines features={features} testID="upgrade-all-benefits-list" />
    </View>
  );
}

/** A hairline between the page's links and "See all Pro benefits". */
export function PlansHairline() {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return <View style={s.hairline} />;
}

/** "See all Pro benefits ⌄" under the page's button; its arrow turns up once the list is open. */
export function BenefitsLink({ open, label, onPress }: { open: boolean; label: string; onPress: () => void }) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <Pressable
      onPress={onPress}
      style={s.more}
      accessibilityRole="button"
      accessibilityState={{ expanded: open }}
      hitSlop={Space.xs}
      testID="upgrade-benefits-toggle"
    >
      <Text style={s.moreText} maxFontSizeMultiplier={PLANS_FONT_SCALE}>
        {label}
      </Text>
      <Icon name={open ? "chevron-up" : "chevron-down"} size={IconSize.xs} color={theme.primary} />
    </Pressable>
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
            <Text style={[s.timelineLabel, index === 0 && s.timelineLabelFirst]} numberOfLines={2} maxFontSizeMultiplier={PLANS_FONT_SCALE}>
              {row.label}
            </Text>
            {row.chip ? (
              <View style={s.chip}>
                <Text style={s.chipText} maxFontSizeMultiplier={PLANS_FONT_SCALE}>
                  {row.chip}
                </Text>
              </View>
            ) : null}
            <Text style={[s.amount, index === 0 && s.amountFirst]} maxFontSizeMultiplier={PLANS_FONT_SCALE}>
              {row.amount}
            </Text>
          </View>
        ))}
      </View>
    </View>
  );
}

/** A small link is about 17pt tall: this makes it a 45pt target. */
const SMALL_LINK_SLOP = { top: 14, bottom: 14, left: Space.xs, right: Space.xs };

/** Privacy, Terms and (when the build can sell) Restore: what a store asks of a subscription
 * page. The renewal is said above the button. */
export function PlansSmallPrint({
  links,
  restore,
}: {
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
    cardItem: { width: "100%", flexDirection: "row", alignItems: "center", gap: Space.xs },
    cardItemHalf: { width: "50%", paddingRight: Space.xs },
    more: { flexDirection: "row", alignItems: "center", gap: Space.xxs, alignSelf: "center", paddingVertical: Space.xxs },
    allBenefits: { paddingHorizontal: Space.md, paddingTop: Space.xxs },
    hairline: { height: StyleSheet.hairlineWidth, backgroundColor: theme.border, marginHorizontal: Space.xl },
    moreText: { ...Type.secondary, ...Weight.semibold, color: theme.primary },
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
    smallLinks: { flexDirection: "row", flexWrap: "wrap", justifyContent: "center" },
    smallLinkRow: { flexDirection: "row", alignItems: "center", gap: Space.md, marginHorizontal: Space.sm },
    smallDivider: { ...Type.caption, color: theme.textTertiary },
    smallLink: { ...Type.caption, ...Weight.semibold, color: theme.textSecondary },
  });
}
