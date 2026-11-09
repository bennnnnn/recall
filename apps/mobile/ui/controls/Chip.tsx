import { useMemo } from "react";
import { Pressable, StyleSheet, Text } from "react-native";

import { selection } from "@/lib/haptics";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";

import { tabRole } from "./a11yRoles";

type Props = {
  label: string;
  /** The current choice: indigo. */
  selected?: boolean;
  onPress: () => void;
  /**
   * `radio` when the choices exclude each other; `tab` for a row that switches what is shown
   * under it (in a `tablist`), read as a button on iOS (`tabRole`).
   */
  accessibilityRole: "radio" | "tab";
  testID?: string;
};

/** One filter chip for the whole app: one choice among several, as Library's and the math keyboard's. */
export function Chip({ label, selected = false, onPress, accessibilityRole, testID }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  // A filter is a selection, like a segment: one tick when the choice changes.
  const press = () => {
    if (!selected) selection();
    onPress();
  };

  return (
    <Pressable
      onPress={press}
      style={({ pressed }) => [s.chip, selected && s.on, pressed && s.pressed]}
      accessibilityRole={accessibilityRole === "tab" ? tabRole() : accessibilityRole}
      accessibilityLabel={label}
      accessibilityState={accessibilityRole === "tab" ? { selected } : { checked: selected }}
      testID={testID}
    >
      <Text style={[s.text, { color: selected ? theme.primary : theme.text }, selected && s.textOn]} numberOfLines={1}>
        {label}
      </Text>
    </Pressable>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    chip: {
      flexDirection: "row",
      alignItems: "center",
      maxWidth: "100%",
      borderRadius: Radius.full,
      minHeight: Space.minTouch,
      paddingHorizontal: Space.md,
      paddingVertical: Space.xs,
      backgroundColor: t.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
    },
    on: { backgroundColor: t.primaryLight, borderColor: t.primary },
    pressed: { opacity: 0.72 },
    text: { ...Type.secondary, ...Weight.medium, flexShrink: 1 },
    textOn: { ...Weight.semibold },
  });
}
