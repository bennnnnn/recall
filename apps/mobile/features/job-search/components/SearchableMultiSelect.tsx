import { useMemo, useState } from "react";
import { Keyboard, Pressable, StyleSheet, Text, View } from "react-native";
import { FlashList } from "@shopify/flash-list";
import { useTranslation } from "react-i18next";

import { Sheet } from "@/ui/overlay/Sheet";
import { Icon } from "@/ui/icons/Icon";
import { SearchField } from "@/ui/controls/SearchField";
import { isValidCustomOption, matchOption, rankedOptions } from "@/features/job-search/model/optionSearch";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";

type Props = {
  values: string[];
  onChange: (values: string[]) => void;
  options: readonly string[];
  /** Field-row placeholder when nothing is selected. */
  placeholder: string;
  sheetTitle: string;
  searchPlaceholder: string;
  maxSelections: number;
  disabled?: boolean;
  /** Parent-level validation error — paints the field border red. */
  invalid?: boolean;
};

/**
 * Indeed-style picker: a field row that opens a sheet with the FULL option
 * list (virtualized, searchable, multi-select with checkmarks). Custom
 * entries are allowed only via isValidCustomOption — "bb" never saves.
 * Selected values show as removable chips under the field.
 */
export function SearchableMultiSelect({
  values,
  onChange,
  options,
  placeholder,
  sheetTitle,
  searchPlaceholder,
  maxSelections,
  disabled,
  invalid,
}: Props) {
  const C = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(C), [C]);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const atMax = values.length >= maxSelections;
  const filtered = useMemo(
    () => rankedOptions(options, query, values),
    [options, query, values],
  );
  const trimmed = query.trim();
  const canAddCustom =
    trimmed.length > 0 && !matchOption(options, trimmed) && isValidCustomOption(trimmed) && !atMax;

  const openSheet = () => {
    if (disabled) return;
    Keyboard.dismiss();
    setQuery("");
    setOpen(true);
  };

  const addValue = (value: string) => {
    if (atMax) return;
    if (values.some((item) => item.toLowerCase() === value.toLowerCase())) return;
    onChange([...values, value]);
    setQuery("");
  };

  const removeValue = (value: string) => {
    onChange(values.filter((item) => item !== value));
  };

  return (
    <View style={s.wrap}>
      <Pressable
        style={({ pressed }) => [
          s.fieldRow,
          pressed && s.pressed,
          disabled && s.disabled,
          invalid && s.fieldError,
        ]}
        onPress={openSheet}
        disabled={disabled}
        accessibilityRole="button"
      >
        <Icon name="search" size={18} color={C.textTertiary} />
        <Text
          style={values.length > 0 ? s.fieldValue : s.fieldPlaceholder}
          numberOfLines={2}
        >
          {values.length > 0 ? values.join(", ") : placeholder}
        </Text>
        <Icon name="chevron-down" size={18} color={C.textTertiary} />
      </Pressable>

      {values.length > 0 ? (
        <View style={s.chips}>
          {values.map((value) => (
            <View key={value.toLowerCase()} style={s.chip}>
              <Text style={s.chipText}>{value}</Text>
              <Pressable
                onPress={() => removeValue(value)}
                disabled={disabled}
                hitSlop={8}
                accessibilityRole="button"
                accessibilityLabel={t("my_job.role_remove_a11y", { role: value })}
                style={({ pressed }) => [s.chipRemove, pressed && s.pressed]}
              >
                <Icon name="close" size={14} color={C.primary} />
              </Pressable>
            </View>
          ))}
        </View>
      ) : null}

      {atMax ? (
        <Text style={s.maxHint}>{t("my_job.picker_max_reached", { max: maxSelections })}</Text>
      ) : null}

      <Sheet
        visible={open}
        onClose={() => setOpen(false)}
        variant="bottom"
        withHandle
        floating
        keyboardAvoiding
        minBottomPadding={12}
        contentContainerStyle={s.sheetContent}
      >
        <Text style={s.sheetTitle}>{sheetTitle}</Text>
        {atMax ? (
          <Text style={s.sheetMaxHint}>
            {t("my_job.picker_max_reached", { max: maxSelections })}
          </Text>
        ) : null}
        <SearchField
          value={query}
          onChangeText={setQuery}
          placeholder={searchPlaceholder}
          autoCapitalize="words"
          autoFocus
        />
        <View style={s.sheetList}>
          <FlashList
            data={filtered}
            keyExtractor={(item) => item}
            keyboardShouldPersistTaps="handled"
            ListFooterComponent={
              canAddCustom ? (
                <Pressable
                  style={({ pressed }) => [s.sheetRow, pressed && s.sheetRowPressed]}
                  onPress={() => addValue(trimmed)}
                  accessibilityRole="button"
                >
                  <Icon name="pencil-outline" size={18} color={C.textSecondary} />
                  <Text style={s.customText} numberOfLines={1}>
                    {t("my_job.role_add_custom", { text: trimmed })}
                  </Text>
                </Pressable>
              ) : null
            }
            renderItem={({ item }) => (
              <Pressable
                style={({ pressed }) => [
                  s.sheetRow,
                  pressed && s.sheetRowPressed,
                  atMax && s.disabled,
                ]}
                onPress={() => addValue(item)}
                disabled={atMax}
                accessibilityRole="button"
              >
                <Icon name="add-circle-outline" size={20} color={C.primary} />
                <Text style={s.sheetRowText} numberOfLines={1}>
                  {item}
                </Text>
              </Pressable>
            )}
          />
        </View>
        <Pressable
          style={({ pressed }) => [s.doneButton, pressed && s.pressed]}
          onPress={() => setOpen(false)}
          accessibilityRole="button"
        >
          <Text style={s.doneText}>{t("my_job.picker_done")}</Text>
        </Pressable>
      </Sheet>
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    wrap: { gap: Space.xs },
    fieldRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      minHeight: 54,
      borderRadius: Radius.xl,
      backgroundColor: C.surface,
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
    },
    fieldError: { borderColor: C.danger },
    fieldValue: { ...Type.body, color: C.text, flex: 1 },
    fieldPlaceholder: { ...Type.body, color: C.textDisabled, flex: 1 },
    chips: {
      flexDirection: "row",
      flexWrap: "wrap",
      gap: Space.xs,
    },
    chip: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
      minHeight: 34,
      paddingLeft: Space.sm,
      paddingRight: 6,
      borderRadius: Radius.full,
      backgroundColor: C.primaryLight,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.primary,
    },
    chipText: { ...Type.secondary, ...Weight.semibold, color: C.primary },
    chipRemove: {
      width: 24,
      height: 24,
      borderRadius: Radius.full,
      alignItems: "center",
      justifyContent: "center",
    },
    maxHint: { ...Type.caption, color: C.textTertiary },
    sheetContent: { gap: Space.sm },
    sheetTitle: {
      ...Type.label,
      color: C.text,
      textAlign: "center",
      paddingBottom: Space.xxs,
    },
    sheetMaxHint: { ...Type.caption, color: C.warning, textAlign: "center" },
    sheetList: { height: 380 },
    sheetRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      minHeight: 48,
      paddingHorizontal: Space.sm,
      borderRadius: Radius.md,
    },
    sheetRowPressed: { backgroundColor: C.surfaceAlt },
    sheetRowText: { ...Type.body, color: C.text, flex: 1 },
    customText: { ...Type.secondary, color: C.textSecondary, flex: 1 },
    doneButton: {
      minHeight: 50,
      borderRadius: Radius.full,
      backgroundColor: C.primary,
      alignItems: "center",
      justifyContent: "center",
    },
    doneText: { ...Type.label, color: C.onPrimary },
    pressed: { opacity: 0.72 },
    disabled: { opacity: 0.45 },
  });
}
