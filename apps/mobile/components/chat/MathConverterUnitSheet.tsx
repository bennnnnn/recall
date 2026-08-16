import { useMemo } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { Theme, useTheme } from "@/lib/theme";
import {
  UNIT_CATEGORIES,
  UNITS_BY_CATEGORY,
  type UnitCategory,
} from "@/lib/unitConverter";

/** Fixed so Length / Temp / Volume don't bounce the sheet when the list length changes. */
const UNIT_PICKER_SHEET_HEIGHT = 520;
const UNIT_PICKER_LIST_HEIGHT = 360;

type Props = {
  visible: boolean;
  category: UnitCategory;
  selectedId: string;
  onClose: () => void;
  onPickCategory: (category: UnitCategory) => void;
  onPickUnit: (id: string) => void;
};

export function MathConverterUnitSheet({
  visible,
  category,
  selectedId,
  onClose,
  onPickCategory,
  onPickUnit,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <AppSheet
      visible={visible}
      onClose={onClose}
      variant="bottom"
      withHandle
      floating
      minBottomPadding={12}
      contentContainerStyle={s.sheet}
    >
      <View style={s.header}>
        <Text style={s.title}>{t("chat.math_converter_select_unit")}</Text>
        <Pressable onPress={onClose} hitSlop={8} testID="math-converter-picker-close">
          <Text style={s.close}>×</Text>
        </Pressable>
      </View>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={s.cats}
      >
        {UNIT_CATEGORIES.map((id) => {
          const selected = id === category;
          return (
            <Pressable
              key={id}
              onPress={() => onPickCategory(id)}
              style={[s.cat, selected && s.catSelected]}
              testID={`math-converter-cat-${id}`}
            >
              <Text style={[s.catLabel, selected && s.catLabelSelected]}>
                {t(`chat.math_converter_cat_${id}`)}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>
      <ScrollView
        style={s.list}
        testID="math-converter-picker"
        keyboardShouldPersistTaps="handled"
      >
        {UNITS_BY_CATEGORY[category].map((unit) => {
          const selected = unit.id === selectedId;
          return (
            <Pressable
              key={unit.id}
              onPress={() => onPickUnit(unit.id)}
              style={s.unitRow}
              testID={`math-converter-unit-${unit.id}`}
            >
              <Text style={[s.unitName, selected && s.unitNameSelected]}>
                {unit.name} ({unit.symbol})
              </Text>
              <View style={[s.radio, selected && s.radioOn]} />
            </Pressable>
          );
        })}
      </ScrollView>
    </AppSheet>
  );
}

const makeStyles = (theme: Theme) =>
  StyleSheet.create({
    sheet: {
      backgroundColor: theme.surface,
      paddingHorizontal: 16,
      paddingTop: 8,
      paddingBottom: 8,
      height: UNIT_PICKER_SHEET_HEIGHT,
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      marginBottom: 10,
    },
    title: { fontSize: 17, fontWeight: "700", color: theme.text },
    close: { fontSize: 24, color: theme.textSecondary, paddingHorizontal: 4 },
    cats: { gap: 8, paddingBottom: 12 },
    cat: {
      paddingHorizontal: 12,
      paddingVertical: 8,
      borderRadius: 16,
      backgroundColor: theme.surfaceAlt,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    catSelected: { backgroundColor: theme.primaryLight, borderColor: theme.primary },
    catLabel: { fontSize: 14, fontWeight: "600", color: theme.textSecondary },
    catLabelSelected: { color: theme.primary },
    list: { height: UNIT_PICKER_LIST_HEIGHT },
    unitRow: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingVertical: 14,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: theme.border,
    },
    unitName: { fontSize: 16, color: theme.text },
    unitNameSelected: { color: theme.primary, fontWeight: "700" },
    radio: {
      width: 18,
      height: 18,
      borderRadius: 9,
      borderWidth: 1.5,
      borderColor: theme.border,
    },
    radioOn: { borderColor: theme.primary, backgroundColor: theme.primary },
  });
