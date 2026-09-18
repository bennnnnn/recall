import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { AUTOMATION_FREQUENCIES, type AutomationFrequency } from "@/lib/api/types";
import { automationFrequencyMessageKey } from "@/lib/automations/frequency";
import { selection } from "@/lib/haptics";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

export { automationFrequencyMessageKey } from "@/lib/automations/frequency";

/** Pick-one list for automation frequency. Must live in the parent sheet — a
 * nested AppSheet never presents on iOS (mirrors RepeatPickerSheet). */
export function AutomationFrequencyPicker({
  selected,
  onSelect,
}: {
  selected: AutomationFrequency;
  onSelect: (frequency: AutomationFrequency) => void;
}) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);

  const pick = (frequency: AutomationFrequency) => {
    selection();
    onSelect(frequency);
  };

  return (
    <View style={s.menu}>
      {AUTOMATION_FREQUENCIES.map((frequency) => {
        const active = frequency === selected;
        const label = t(automationFrequencyMessageKey(frequency));
        return (
          <Pressable
            key={frequency}
            style={({ pressed }) => [s.item, active && s.itemActive, pressed && s.itemPressed]}
            onPress={() => pick(frequency)}
            accessibilityRole="radio"
            accessibilityState={{ selected: active }}
            accessibilityLabel={label}
          >
            <Text style={[s.label, active && s.labelActive]}>{label}</Text>
            {active ? <Icon name="checkmark" size={18} color={theme.primary} /> : null}
          </Pressable>
        );
      })}
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    menu: {
      borderWidth: 1,
      borderColor: C.border,
      borderTopWidth: 0,
      borderBottomLeftRadius: Radius.md,
      borderBottomRightRadius: Radius.md,
      overflow: "hidden",
      backgroundColor: C.surface,
    },
    item: {
      flexDirection: "row",
      alignItems: "center",
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      gap: Space.sm,
      minHeight: Space.minTouch,
    },
    itemPressed: { backgroundColor: C.surfaceAlt },
    itemActive: { backgroundColor: C.primaryLight },
    label: { ...Type.navTitle, fontWeight: "400", color: C.text, flex: 1 },
    labelActive: { fontWeight: "600", color: C.primary },
  });
}
