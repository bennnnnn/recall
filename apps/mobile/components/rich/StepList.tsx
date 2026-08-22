import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";

import { RichBodyText } from "@/components/rich/RichBodyText";
import { Theme, useTheme } from "@/lib/theme";

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
    wrap: { marginVertical: 8, gap: 10 },
    row: {
      flexDirection: "row",
      gap: 10,
      alignItems: "flex-start",
    },
    badge: {
      width: 24,
      height: 24,
      borderRadius: 12,
      backgroundColor: t.primaryLight,
      alignItems: "center",
      justifyContent: "center",
      flexShrink: 0,
      marginTop: 2,
    },
    badgeText: { fontSize: 13, fontWeight: "700", color: t.primary },
    text: { flex: 1, fontSize: 16, lineHeight: 24, color: t.text },
  });
}
