/**
 * The plans sheet's parts: the paid plans as tiles side by side (name, price, the day's
 * messages), what the picked plan gives as a checklist, and the small print. A tile is
 * picked with a tap; the sheet's one button buys it.
 */
import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { Icon } from "@/ui/icons/Icon";
import type { IconName } from "@/ui/icons/names";
import { IconSize } from "@/ui/icons/sizes";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { getLegalPrivacyUrl, getLegalTermsUrl } from "@/lib/legalUrls";
import { openAllowedUrl } from "@/lib/linkSchemePolicy";
import { Theme, useTheme, withAlpha } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";

export type FeatureLine = { icon: IconName; text: string; note?: string };

export type Tile = {
  id: string;
  name: string;
  /** The store's price ("$7.99"); none until the store says, and then the tile shows none. */
  price?: string;
  perMonth: string;
  headline: string;
};

export function PlanTiles({
  tiles,
  picked,
  onPick,
  disabled,
}: {
  tiles: readonly Tile[];
  picked: string | null;
  onPick: (id: string) => void;
  disabled?: boolean;
}) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <View style={s.tiles}>
      {tiles.map((tile) => {
        const on = tile.id === picked;
        return (
          <Pressable
            key={tile.id}
            onPress={() => onPick(tile.id)}
            disabled={disabled}
            style={[s.tile, on && s.tileOn]}
            accessibilityRole="radio"
            accessibilityState={{ checked: on, disabled }}
            accessibilityLabel={[tile.name, tile.price && `${tile.price}${tile.perMonth}`, tile.headline]
              .filter(Boolean)
              .join(", ")}
            testID={`upgrade-plan-${tile.id}`}
          >
            <View style={s.tileTop}>
              <Text style={[s.tileName, on && s.tileNameOn]}>{tile.name}</Text>
              <View style={[s.radio, on && s.radioOn]}>
                {on ? <Icon name="check" size={IconSize.xxs} color={theme.onPrimary} /> : null}
              </View>
            </View>
            {tile.price ? (
              <Text style={s.price}>
                {tile.price}
                <Text style={s.perMonth}>{tile.perMonth}</Text>
              </Text>
            ) : null}
            <Text style={s.headline}>{tile.headline}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function PlanBenefits({ heading, lines }: { heading: string; lines: readonly FeatureLine[] }) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <View style={s.benefits}>
      <Text style={s.benefitsHeading}>{heading}</Text>
      {lines.map((line) => (
        <View key={line.text} style={s.benefit}>
          <View style={s.benefitIcon}>
            <Icon name={line.icon} size={IconSize.xs} color={theme.primary} />
          </View>
          <Text style={s.benefitText}>
            {line.text}
            {line.note ? <Text style={s.benefitNote}>{`  ${line.note}`}</Text> : null}
          </Text>
        </View>
      ))}
    </View>
  );
}

/** A small link is about 17pt tall: this makes it a 45pt target. */
const SMALL_LINK_SLOP = { top: 14, bottom: 14, left: Space.xs, right: Space.xs };

/** The subscription's renewal and the Terms and Privacy links that a store asks of a
 * subscription screen, in the smallest type, after Restore when the build can sell. */
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
    ...(restore ? [{ label: restore.label, onPress: restore.onPress, disabled: restore.disabled }] : []),
    { label: links.terms, onPress: () => void openAllowedUrl(getLegalTermsUrl()), disabled: false },
    { label: links.privacy, onPress: () => void openAllowedUrl(getLegalPrivacyUrl()), disabled: false },
  ];
  return (
    <View style={s.small}>
      <Text style={s.smallText}>{renews}</Text>
      <View style={s.smallLinks}>
        {items.map((item, index) => (
          <View key={item.label} style={s.smallLinkRow}>
            {index > 0 ? (
              <Text style={s.smallText} accessibilityElementsHidden importantForAccessibility="no">
                ·
              </Text>
            ) : null}
            <Pressable
              onPress={item.onPress}
              disabled={item.disabled}
              accessibilityRole={index === 0 && restore ? "button" : "link"}
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
    tiles: { flexDirection: "row", gap: Space.sm },
    tile: {
      flex: 1,
      minWidth: 0,
      borderRadius: Radius.lg,
      borderWidth: 1.5,
      borderColor: theme.border,
      backgroundColor: theme.surface,
      padding: Space.md,
      gap: Space.xxs,
    },
    tileOn: { borderColor: theme.primary, backgroundColor: withAlpha(theme.primary, theme.isDark ? 0.18 : 0.07) },
    tileTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
    tileName: { ...Type.body, ...Weight.semibold, color: theme.textSecondary },
    tileNameOn: { color: theme.primary },
    radio: {
      width: 20,
      height: 20,
      borderRadius: Radius.full,
      borderWidth: 1.5,
      borderColor: theme.borderStrong,
      alignItems: "center",
      justifyContent: "center",
    },
    radioOn: { borderColor: theme.primary, backgroundColor: theme.primary },
    price: { ...Type.title, ...Weight.bold, color: theme.text, marginTop: Space.xxs },
    perMonth: { ...Type.caption, ...Weight.regular, color: theme.textSecondary },
    headline: { ...Type.caption, ...Weight.semibold, color: theme.textSecondary },
    benefits: { gap: Space.sm },
    benefitsHeading: { ...Type.overline, color: theme.textTertiary },
    benefit: { flexDirection: "row", alignItems: "center", gap: Space.sm },
    benefitIcon: {
      width: 28,
      height: 28,
      borderRadius: Radius.md,
      backgroundColor: theme.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    benefitText: { flex: 1, ...Type.body, color: theme.text },
    benefitNote: { ...Type.caption, color: theme.textTertiary },
    small: { gap: Space.xxs, alignItems: "center" },
    smallText: { ...Type.caption, ...Weight.regular, color: theme.textTertiary, textAlign: "center" },
    smallLinks: { flexDirection: "row", flexWrap: "wrap", justifyContent: "center" },
    smallLinkRow: { flexDirection: "row", alignItems: "center", gap: Space.xs, marginHorizontal: Space.xxs },
    smallLink: { ...Type.caption, ...Weight.semibold, color: theme.textSecondary },
  });
}
