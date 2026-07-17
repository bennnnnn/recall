import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { Button } from "@/components/Button";
import { Theme, useTheme } from "@/lib/theme";

export type StepPickerOption<T> = {
  key: string;
  value: T;
  label: string;
};

type Props<T> = {
  label: string;
  hint: string;
  options: StepPickerOption<T>[];
  isSelected: (value: T) => boolean;
  onSelect: (value: T) => void;
  backLabel: string;
  onBack: () => void;
  continueLabel: string;
  onContinue: () => void;
  /** Disables continue and swaps its label for a spinner (e.g. the final create-project submit). */
  continueBusy?: boolean;
};

/**
 * One step of the project-creation flow: a label, a hint, a list of
 * tappable options (single- or multi-select — the caller's `onSelect`
 * decides which, this component only reflects `isSelected`), and a
 * back/continue action row. Shared by the level/topics/trivia-difficulty/
 * daily-goal steps in app/projects/index.tsx, which were previously four
 * separately hand-written ~40-line copies of this exact structure.
 */
export function StepPicker<T>({
  label,
  hint,
  options,
  isSelected,
  onSelect,
  backLabel,
  onBack,
  continueLabel,
  onContinue,
  continueBusy = false,
}: Props<T>) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <>
      <Text style={s.label}>{label}</Text>
      <Text style={s.hint}>{hint}</Text>
      <View style={s.list}>
        {options.map((option) => {
          const selected = isSelected(option.value);
          return (
            <Pressable
              key={option.key}
              style={[s.row, selected && s.rowActive]}
              accessibilityRole="radio"
              accessibilityState={{ selected }}
              accessibilityLabel={option.label}
              onPress={() => onSelect(option.value)}
            >
              <Text style={[s.rowText, selected && s.rowTextActive]}>{option.label}</Text>
              {selected ? <Ionicons name="checkmark" size={18} color={theme.primary} /> : null}
            </Pressable>
          );
        })}
      </View>
      <View style={s.actions}>
        <Button title={backLabel} onPress={onBack} variant="outline" style={s.actionBtn} />
        <Button
          title={continueLabel}
          onPress={onContinue}
          loading={continueBusy}
          style={s.actionBtn}
        />
      </View>
    </>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    label: { fontSize: 20, fontWeight: "700", color: theme.text },
    hint: { fontSize: 14, color: theme.textSecondary, marginBottom: 4 },
    list: { gap: 8 },
    row: {
      flexDirection: "row",
      alignItems: "center",
      gap: 12,
      paddingVertical: 14,
      paddingHorizontal: 12,
      borderRadius: 14,
      backgroundColor: theme.surface,
      borderWidth: 1,
      borderColor: theme.border,
    },
    rowActive: { borderColor: theme.primary, backgroundColor: theme.primaryLight },
    rowText: { fontSize: 16, fontWeight: "600", color: theme.text },
    rowTextActive: { color: theme.primaryDark },
    actions: { flexDirection: "row", gap: 10, marginTop: 8 },
    actionBtn: { flex: 1 },
  });
}
