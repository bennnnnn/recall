/**
 * One paid plan on the plans sheet: a card the user taps to pick, with its price and what
 * it includes. The sheet's one button below buys the picked plan, so a card holds no button.
 */
import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { Icon } from "@/ui/icons/Icon";
import type { IconName } from "@/ui/icons/names";
import { IconSize } from "@/ui/icons/sizes";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";

export type FeatureLine = { icon: IconName; text: string };

type Props = {
  name: string;
  price: string;
  lines: readonly FeatureLine[];
  picked: boolean;
  onPick: () => void;
  disabled?: boolean;
  testID?: string;
};

export function PlanCard({ name, price, lines, picked, onPick, disabled, testID }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <Pressable
      onPress={onPick}
      disabled={disabled}
      style={[s.card, picked && s.picked]}
      accessibilityRole="radio"
      accessibilityState={{ checked: picked, disabled }}
      accessibilityLabel={`${name}, ${price}`}
      testID={testID}
    >
      <View style={s.header}>
        <View style={[s.radio, picked && s.radioPicked]}>
          {picked ? <Icon name="check" size={IconSize.xs} color={theme.onPrimary} /> : null}
        </View>
        <Text style={s.name}>{name}</Text>
        <Text style={[s.price, picked && s.pricePicked]}>{price}</Text>
      </View>
      <View style={s.lines}>
        {lines.map((line) => (
          <View key={line.text} style={s.line}>
            <Icon name={line.icon} size={IconSize.sm} color={theme.primary} />
            <Text style={s.lineText}>{line.text}</Text>
          </View>
        ))}
      </View>
    </Pressable>
  );
}

const RADIO = 22;

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    card: {
      borderRadius: Radius.lg,
      borderWidth: 1.5,
      borderColor: theme.border,
      backgroundColor: theme.surface,
      padding: Space.md,
      gap: Space.sm,
    },
    picked: { borderColor: theme.primary, backgroundColor: theme.primaryLight },
    header: { flexDirection: "row", alignItems: "center", gap: Space.sm },
    radio: {
      width: RADIO,
      height: RADIO,
      borderRadius: Radius.full,
      borderWidth: 1.5,
      borderColor: theme.borderStrong,
      alignItems: "center",
      justifyContent: "center",
    },
    radioPicked: { borderColor: theme.primary, backgroundColor: theme.primary },
    name: { ...Type.body, ...Weight.semibold, color: theme.text, flex: 1 },
    price: { ...Type.secondary, ...Weight.semibold, color: theme.textSecondary },
    pricePicked: { color: theme.text },
    lines: { gap: Space.xs, paddingLeft: RADIO + Space.sm },
    line: { flexDirection: "row", alignItems: "center", gap: Space.xs },
    lineText: { flex: 1, ...Type.secondary, color: theme.textSecondary },
  });
}
