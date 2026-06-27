import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { Theme, useTheme } from "@/lib/theme";

type Props = {
  model?: string | null;
};

const MODEL_LABELS: Record<string, string> = {
  "free-chat": "Free",
  "smart-chat": "Smart",
  "max-chat": "Max",
  auto: "Auto",
};

export function MessageMetaChips({ model }: Props) {
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  if (!model) return null;

  return (
    <View style={s.wrap}>
      <View style={[s.chip, s.chipMuted]}>
        <Ionicons name="hardware-chip-outline" size={12} color={C.textTertiary} />
        <Text style={[s.chipText, s.chipTextMuted]} numberOfLines={1}>
          {MODEL_LABELS[model] ?? model}
        </Text>
      </View>
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    wrap: {
      flexDirection: "row",
      flexWrap: "wrap",
      gap: 6,
      marginTop: 8,
      paddingHorizontal: 2,
    },
    chip: {
      flexDirection: "row",
      alignItems: "center",
      gap: 4,
      paddingHorizontal: 8,
      paddingVertical: 4,
      borderRadius: 999,
    },
    chipMuted: { backgroundColor: C.surface },
    chipText: { fontSize: 12, fontWeight: "600", maxWidth: 180 },
    chipTextMuted: { color: C.textSecondary, fontWeight: "500" },
  });
}
