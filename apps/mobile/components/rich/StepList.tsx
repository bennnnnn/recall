import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";

import { RichBodyText } from "@/components/rich/RichBodyText";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";

type Props = { steps: string[] };

export function StepList({ steps }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <View style={s.wrap}>
      {steps.map((step, index) => (
        <View key={`step-${index}`} style={s.row}>
          <View style={s.badge}>
            <Text style={s.badgeText}>{index + 1}</Text>
          </View>
          <RichBodyText style={s.text} selectable>
            {step}
          </RichBodyText>
        </View>
      ))}
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: { marginVertical: Space.xs, gap: 10 },
    row: {
      flexDirection: "row",
      gap: 10,
      alignItems: "flex-start",
    },
    badge: {
      width: 24,
      height: 24,
      borderRadius: Radius.md,
      backgroundColor: t.primaryLight,
      alignItems: "center",
      justifyContent: "center",
      flexShrink: 0,
      marginTop: 2,
    },
    badgeText: { ...Type.compact, ...Weight.bold, color: t.primary },
    text: { flex: 1, ...Type.body, lineHeight: 24, color: t.text },
  });
}
