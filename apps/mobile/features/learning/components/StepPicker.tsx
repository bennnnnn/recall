import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Icon } from "@/ui/icons/Icon";

import { Button } from "@/ui/controls/Button";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { IconSize } from "@/ui/icons/sizes";

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
 * back/continue action row. Used by the daily-goal step on
 * `app/projects/create.tsx`.
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
              accessibilityState={{ selected, disabled: continueBusy }}
              disabled={continueBusy}
              accessibilityLabel={option.label}
              onPress={() => onSelect(option.value)}
            >
              <Text style={[s.rowText, selected && s.rowTextActive]}>{option.label}</Text>
              {selected ? <Icon name="check" size={IconSize.sm} color={theme.primary} /> : null}
            </Pressable>
          );
        })}
      </View>
      <View style={s.actions}>
        <Button
          title={backLabel}
          onPress={onBack}
          variant="outline"
          disabled={continueBusy}
          style={s.actionBtn}
        />
        <Button
          title={continueLabel}
          onPress={onContinue}
          loading={continueBusy}
          loadingLabel={continueLabel}
          disabled={continueBusy}
          style={s.actionBtn}
        />
      </View>
    </>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    label: { ...Type.title, ...Weight.bold, color: theme.text },
    hint: { ...Type.secondary, color: theme.textSecondary, marginBottom: Space.xxs },
    list: { gap: Space.xs },
    row: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      paddingVertical: 14,
      paddingHorizontal: Space.sm,
      borderRadius: Radius.lg,
      backgroundColor: theme.surface,
      borderWidth: 1,
      borderColor: theme.border,
    },
    rowActive: { borderColor: theme.primary, backgroundColor: theme.primaryLight },
    rowText: { ...Type.body, ...Weight.semibold, color: theme.text },
    rowTextActive: { color: theme.primaryDark },
    actions: { flexDirection: "row", gap: 10, marginTop: Space.xs },
    actionBtn: { flex: 1 },
  });
}
