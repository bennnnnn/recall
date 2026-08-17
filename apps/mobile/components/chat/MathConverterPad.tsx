import { memo, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Icon } from "@/components/Icon";
import { useTranslation } from "react-i18next";

import { MathConverterUnitSheet } from "@/components/chat/MathConverterUnitSheet";
import { selection as hapticSelection } from "@/lib/haptics";
import { Theme, useTheme } from "@/lib/theme";
import {
  CONVERTER_DEFAULT_DIGITS,
  appendConverterDigit,
  convertUnit,
  converterAskText,
  defaultUnits,
  findUnit,
  formatConvertNumber,
  type UnitCategory,
} from "@/lib/unitConverter";

type Props = {
  onAsk: (text: string) => void;
  onStop: () => void;
  streaming: boolean;
};

function buzz() {
  hapticSelection();
}

export const MathConverterPad = memo(function MathConverterPad({
  onAsk,
  onStop,
  streaming,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [category, setCategory] = useState<UnitCategory>("length");
  const [fromId, setFromId] = useState("m");
  const [toId, setToId] = useState("cm");
  const [digits, setDigits] = useState(CONVERTER_DEFAULT_DIGITS);
  const [fresh, setFresh] = useState(true);
  const [pickerFor, setPickerFor] = useState<"from" | "to" | null>(null);

  const from = findUnit(fromId);
  const to = findUnit(toId);
  const parsed = Number(digits);
  const raw = Number.isFinite(parsed) ? convertUnit(parsed, fromId, toId) : null;
  const result = raw == null ? "—" : formatConvertNumber(raw);

  const typeKey = (key: string) => {
    buzz();
    const next = appendConverterDigit(digits, key, fresh);
    setDigits(next);
    setFresh(key === "AC" || (key === "back" && next === CONVERTER_DEFAULT_DIGITS));
  };

  const pickCategory = (next: UnitCategory) => {
    setCategory(next);
    const defaults = defaultUnits(next);
    setFromId(defaults.fromId);
    setToId(defaults.toId);
  };

  const pickUnit = (id: string) => {
    if (pickerFor === "from") setFromId(id);
    if (pickerFor === "to") setToId(id);
    setPickerFor(null);
  };

  const ask = () => {
    buzz();
    if (streaming) {
      onStop();
      return;
    }
    if (!from || !to) return;
    onAsk(converterAskText(digits, from.prompt, to.prompt));
  };

  return (
    <View style={s.wrap} testID="math-converter">
      <View style={s.io}>
        <View style={s.col}>
          <Text style={s.value} numberOfLines={1} testID="math-converter-from-value">
            {digits}
          </Text>
          <UnitChip
            symbol={from?.symbol ?? ""}
            testID="math-converter-from-unit"
            onPress={() => setPickerFor("from")}
            theme={theme}
          />
        </View>
        <Pressable
          onPress={() => {
            buzz();
            setFromId(toId);
            setToId(fromId);
            if (raw != null && Number.isFinite(raw)) {
              setDigits(formatConvertNumber(raw));
              setFresh(false);
            }
          }}
          style={({ pressed }) => [s.swap, pressed && s.pressed]}
          accessibilityRole="button"
          accessibilityLabel={t("chat.math_converter_swap")}
          testID="math-converter-swap"
        >
          <Icon name="swap-horizontal" size={18} color={theme.primary} />
        </Pressable>
        <View style={s.col}>
          <Text style={[s.value, s.valueOut]} numberOfLines={1} testID="math-converter-to-value">
            {result}
          </Text>
          <UnitChip
            symbol={to?.symbol ?? ""}
            testID="math-converter-to-unit"
            onPress={() => setPickerFor("to")}
            theme={theme}
          />
        </View>
      </View>
      <View style={s.pad} testID="math-converter-numpad">
        {CONVERTER_PAD.map((row, r) => (
          <View key={r} style={s.row}>
            {row.map((cell) =>
              cell === "ask" ? (
                <Key
                  key={cell}
                  label={streaming ? t("chat.stop") : t("chat.math_converter_ask")}
                  testID="math-converter-ask"
                  onPress={ask}
                  theme={theme}
                  accent
                  trailing={streaming ? "■" : "↑"}
                />
              ) : (
                <Key
                  key={cell}
                  label={cell === "back" ? "⌫" : cell === "AC" ? t("chat.math_converter_clear") : cell}
                  testID={`math-converter-${cell === "back" ? "back" : cell === "." ? "dot" : cell}`}
                  onPress={() => typeKey(cell)}
                  theme={theme}
                  accent={cell === "AC" || cell === "back" || cell === "±"}
                />
              ),
            )}
          </View>
        ))}
      </View>
      <MathConverterUnitSheet
        visible={pickerFor != null}
        category={category}
        selectedId={pickerFor === "to" ? toId : fromId}
        onClose={() => setPickerFor(null)}
        onPickCategory={pickCategory}
        onPickUnit={pickUnit}
      />
    </View>
  );
});

const CONVERTER_PAD = [
  ["7", "8", "9", "AC"],
  ["4", "5", "6", "back"],
  ["1", "2", "3", "±"],
  ["0", ".", "ask"],
] as const;

function UnitChip({
  symbol,
  testID,
  onPress,
  theme,
}: {
  symbol: string;
  testID: string;
  onPress: () => void;
  theme: Theme;
}) {
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [s.unitBtn, pressed && s.pressed]}
      testID={testID}
    >
      <Text style={s.unitBtnLabel}>{symbol}</Text>
      <Icon name="chevron-down" size={14} color={theme.primary} />
    </Pressable>
  );
}

function Key({
  label,
  testID,
  onPress,
  theme,
  accent,
  trailing,
}: {
  label: string;
  testID: string;
  onPress: () => void;
  theme: Theme;
  accent?: boolean;
  trailing?: string;
}) {
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [s.key, accent && s.keyAccent, pressed && s.pressed]}
      accessibilityRole="button"
      accessibilityLabel={label}
      testID={testID}
    >
      <View style={s.keyInner}>
        <Text style={s.keyLabel}>{label}</Text>
        {trailing ? <Text style={s.keyTrailing}>{trailing}</Text> : null}
      </View>
    </Pressable>
  );
}

const makeStyles = (theme: Theme) =>
  StyleSheet.create({
    wrap: { flex: 1, gap: 8 },
    io: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 2 },
    col: { flex: 1, gap: 6, minWidth: 0 },
    value: {
      fontSize: 22,
      fontWeight: "700",
      color: theme.text,
      paddingHorizontal: 4,
      minHeight: 30,
    },
    valueOut: { color: theme.textSecondary, fontWeight: "600" },
    unitBtn: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 4,
      minHeight: 40,
      paddingHorizontal: 10,
      borderRadius: 8,
      backgroundColor: theme.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    unitBtnLabel: { fontSize: 16, fontWeight: "700", color: theme.text },
    swap: { paddingHorizontal: 4, paddingVertical: 6 },
    pad: { gap: 6, marginTop: 2 },
    row: { flexDirection: "row", alignItems: "stretch", gap: 6 },
    key: {
      flex: 1,
      height: 42,
      borderRadius: 8,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: theme.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    keyAccent: { backgroundColor: theme.primaryLight },
    keyInner: { flexDirection: "row", alignItems: "center", gap: 4 },
    keyLabel: { fontSize: 17, fontWeight: "600", color: theme.text },
    keyTrailing: { fontSize: 16, fontWeight: "700", color: theme.primary },
    pressed: { opacity: 0.55, transform: [{ scale: 0.97 }] },
  });
