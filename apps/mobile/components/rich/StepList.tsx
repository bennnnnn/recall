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
        <View key={`step-${index}`} style={[s.row, index > 0 && s.rowGap]}>
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
    wrap: { marginVertical: 8, gap: 0 },
    row: {
      flexDirection: "row",
      gap: 12,
      alignItems: "flex-start",
      backgroundColor: t.bg,
      borderRadius: 12,
      borderWidth: 1,
      borderColor: t.border,
      paddingHorizontal: 12,
      paddingVertical: 12,
    },
    rowGap: { marginTop: 8 },
    badge: {
      width: 28,
      height: 28,
      borderRadius: 14,
      backgroundColor: t.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    badgeText: { fontSize: 14, fontWeight: "700", color: t.primary },
    text: { flex: 1, fontSize: 16, lineHeight: 24, color: t.text, paddingTop: 2 },
  });
}
