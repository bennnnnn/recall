import { memo, useMemo, useState, type ReactNode } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { Icon } from "@/ui/icons/Icon";
import { useTranslation } from "react-i18next";

import { converterKeyHeight, MathConverterPad } from "@/components/chat/MathConverterPad";
import { selection as hapticSelection } from "@/lib/haptics";
import {
  MATH_KEYBOARD_GROUPS,
  MATH_KEYBOARD_SYMBOLS,
  MATH_NUMPAD_ROWS,
  mathGroupCanToggleDigits,
  symbolA11yLabel,
  symbolRowsForGroup,
  type MathKeyboardGroup,
  type MathKeyboardSymbol,
  type PadCell,
} from "@/lib/math/keyboardSymbols";
import { Theme, useTheme } from "@/lib/theme";
import { IconSize } from "@/ui/icons/sizes";
import { Space } from "@/lib/space";
import { Radius } from "@/lib/radius";

const PAD_PADDING_V = 20;
const PAD_GAP = 6;
const KEY_HEIGHT_MIN = Space.minTouch;

function fillKeyHeight(padHeight: number, tabHeight: number, keyRows: number): number {
  if (keyRows <= 0) return KEY_HEIGHT_MIN;
  const gaps = keyRows * PAD_GAP;
  const inner = padHeight - PAD_PADDING_V - tabHeight - gaps;
  // Every keypad fills the same gray area. Fewer rows get taller keys, not a gap above them.
  return Math.max(32, Math.floor(inner / keyRows));
}

type Props = {
  open: boolean;
  height: number;
  onToggle: () => void;
  onInsert: (spec: MathKeyboardSymbol) => void;
  onAsk: (text: string) => void;
  onStop: () => void;
  streaming: boolean;
  onBackspace: () => void;
  onPaste: () => void;
  group: MathKeyboardGroup;
  onGroupChange: (group: MathKeyboardGroup) => void;
};

function buzz() {
  hapticSelection();
}

export const MathKeyboardBar = memo(function MathKeyboardBar({
  open,
  height,
  onToggle,
  onInsert,
  onAsk,
  onStop,
  streaming,
  onBackspace,
  onPaste,
  group,
  onGroupChange,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [digitsOpen, setDigitsOpen] = useState(false);
  const [tabHeight, setTabHeight] = useState(36);
  const canToggleDigits = mathGroupCanToggleDigits(group);
  const fnRows = useMemo(() => symbolRowsForGroup(group), [group]);
  const symbolKeyRows =
    fnRows.filter((row) => row.length > 0).length + (canToggleDigits && group !== "basics" ? 1 : 0);
  const digitKeyRows = MATH_NUMPAD_ROWS.length + 1;
  const keyHeight = fillKeyHeight(height, tabHeight, digitsOpen ? digitKeyRows : symbolKeyRows);
  const converterRowHeight = converterKeyHeight(
    height - PAD_PADDING_V - Math.max(tabHeight, KEY_HEIGHT_MIN) - PAD_GAP,
  );
  const trigFill = useMemo(
    () => ({
      theta: MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "trig-theta")!,
      pi: MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "trig-pi")!,
    }),
    [],
  );
  const numberFill = useMemo(
    () =>
      ["percent", "pm", "deg", "approx"].map(
        (id) => MATH_KEYBOARD_SYMBOLS.find((spec) => spec.id === id)!,
      ),
    [],
  );
  const trigBottom = useMemo(
    () =>
      ["pi-over-6", "pi-over-4", "pi-over-3", "pi-over-2"].map(
        (id) => MATH_KEYBOARD_SYMBOLS.find((spec) => spec.id === id)!,
      ),
    [],
  );
  const calcBottom = useMemo(
    () =>
      ["partial-x", "dy", "ddt", "prime"].map(
        (id) => MATH_KEYBOARD_SYMBOLS.find((spec) => spec.id === id)!,
      ),
    [],
  );
  const greekBottom = useMemo(
    () =>
      ["iota", "upsilon", "Theta", "Phi"].map(
        (id) => MATH_KEYBOARD_SYMBOLS.find((spec) => spec.id === id)!,
      ),
    [],
  );
  const symbolBottom =
    group === "trig" ? trigBottom : group === "calc" ? calcBottom : group === "greek" ? greekBottom : [];
  const digitSide = digitsOpen
    ? group === "trig"
      ? [trigFill.theta, trigFill.pi, numberFill[0]!, numberFill[1]!]
      : numberFill
    : symbolBottom;
  const changeGroup = (next: MathKeyboardGroup) => {
    setDigitsOpen(false);
    onGroupChange(next);
  };
  const padNav = {
    onInsert,
    onBackspace,
    onOpenDigits: () => setDigitsOpen(true),
    backspaceLabel: t("chat.math_keyboard_backspace"),
    digitsLabel: t("chat.math_keyboard_123"),
    theme,
    styles: s,
    keyHeight,
  };
  const basicsGrid = group === "basics" && !digitsOpen;

  if (!open) return null;

  return (
    <View
      style={[s.pad, { height }]}
      accessibilityLabel={t("chat.math_keyboard_a11y")}
      testID="math-keyboard-pad"
    >
      <View
        style={s.tabs}
        onLayout={(e) => setTabHeight(Math.round(e.nativeEvent.layout.height))}
      >
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={s.tabRow}
          keyboardShouldPersistTaps="handled"
        >
        {MATH_KEYBOARD_GROUPS.map((id) => {
          const selected = id === group;
          return (
            <Pressable
              key={id}
              onPress={() => changeGroup(id)}
              style={[s.tab, selected && s.tabSelected]}
              accessibilityRole="button"
              accessibilityState={{ selected }}
              testID={`math-keyboard-tab-${id}`}
            >
              <Text style={[s.tabLabel, selected && s.tabLabelSelected]}>
                {t(`chat.math_keyboard_group_${id}`)}
              </Text>
            </Pressable>
          );
        })}
        </ScrollView>
        <View style={s.nav}>
        <Pressable
          onPress={() => {
            buzz();
            onPaste();
          }}
          style={({ pressed }) => [s.pasteBtn, pressed && s.pressed]}
          accessibilityRole="button"
          accessibilityLabel={t("chat.math_keyboard_paste")}
          testID="math-keyboard-paste"
        >
          <Icon name="clipboard" size={IconSize.sm} color={theme.primary} />
        </Pressable>
        <Pressable
          onPress={onToggle}
          style={({ pressed }) => [s.abc, pressed && s.pressed]}
          accessibilityRole="button"
          accessibilityLabel={t("chat.math_keyboard_abc")}
          testID="math-keyboard-abc"
        >
          <Text style={s.abcLabel}>{t("chat.math_keyboard_abc")}</Text>
        </Pressable>
        </View>
      </View>
      <View style={s.keys}>
      {group === "converter" ? (
        <MathConverterPad
          keyHeight={converterRowHeight}
          onAsk={onAsk}
          onStop={onStop}
          streaming={streaming}
          onInsert={onInsert}
        />
      ) : (
        <>
      {digitsOpen ? (
        <View style={s.numpad} testID="math-keyboard-numpad">
          {MATH_NUMPAD_ROWS.map((row, r) => (
            <View key={r} style={s.row}>
              {row.map((cell, c) => (
                <PadKey key={`${r}-${c}`} cell={cell} {...padNav} />
              ))}
            </View>
          ))}
        </View>
      ) : (
        fnRows.map((row, r) =>
          row.length === 0 ? null : (
            <View key={r} style={s.row}>
              {row.map((cell, c) => (
                <PadKey key={`${r}-${c}`} cell={cell} {...padNav} />
              ))}
            </View>
          ),
        )
      )}
      {canToggleDigits && !basicsGrid ? (
        <RightControlRow
          leading={
            <>
              <DigitToggle
                label={
                  digitsOpen
                    ? t(`chat.math_keyboard_group_${group}`)
                    : t("chat.math_keyboard_123")
                }
                onPress={() => {
                  buzz();
                  setDigitsOpen((open) => !open);
                }}
                styles={s}
                keyHeight={keyHeight}
              />
              {digitSide.map((spec) => (
                <PadKey key={spec.id} cell={{ kind: "insert", spec }} {...padNav} />
              ))}
            </>
          }
          trailing={<PadKey cell={{ kind: "backspace" }} {...padNav} />}
          leadingCount={1 + digitSide.length}
          styles={s}
        />
      ) : null}
        </>
      )}
      </View>
    </View>
  );
});

type PadStyles = ReturnType<typeof makeStyles>;

const PAD_COLUMNS = 6;

function RightControlRow({
  leading,
  trailing,
  leadingCount,
  styles: s,
}: {
  leading: ReactNode;
  trailing: ReactNode;
  leadingCount: number;
  styles: PadStyles;
}) {
  const spacers = Math.max(0, PAD_COLUMNS - leadingCount - 1);
  return (
    <View style={s.row}>
      {leading}
      {Array.from({ length: spacers }, (_, i) => (
        <View key={i} style={s.keySpacer} />
      ))}
      {trailing}
    </View>
  );
}

function DigitToggle({
  label,
  onPress,
  styles: s,
  keyHeight,
}: {
  label: string;
  onPress: () => void;
  styles: PadStyles;
  keyHeight: number;
}) {
  return (
    <KeyBtn
      label={label}
      testID="math-keyboard-123"
      onPress={onPress}
      accessibilityLabel={label}
      styles={s}
      keyHeight={keyHeight}
    />
  );
}

function PadKey({
  cell,
  onInsert,
  onBackspace,
  onOpenDigits,
  backspaceLabel,
  digitsLabel,
  theme,
  styles: s,
  keyHeight = KEY_HEIGHT_MIN,
}: {
  cell: PadCell;
  onInsert: (spec: MathKeyboardSymbol) => void;
  onBackspace: () => void;
  onOpenDigits: () => void;
  backspaceLabel: string;
  digitsLabel: string;
  theme: Theme;
  styles: PadStyles;
  keyHeight?: number;
}) {
  if (cell.kind === "spacer") {
    return <View style={s.keySpacer} />;
  }
  if (cell.kind === "digits") {
    return (
      <DigitToggle
        label={digitsLabel}
        onPress={() => {
          buzz();
          onOpenDigits();
        }}
        styles={s}
        keyHeight={keyHeight}
      />
    );
  }
  if (cell.kind === "backspace") {
    return (
      <KeyBtn
        testID="math-key-backspace"
        onPress={() => {
          buzz();
          onBackspace();
        }}
        accessibilityLabel={backspaceLabel}
        styles={s}
        keyHeight={keyHeight}
        danger
      >
        <Icon name="backspace" size={IconSize.sm} color={theme.danger} />
      </KeyBtn>
    );
  }
  return (
    <KeyBtn
      label={cell.spec.label}
      testID={`math-key-${cell.spec.id}`}
      onPress={() => {
        buzz();
        onInsert(cell.spec);
      }}
      accessibilityLabel={symbolA11yLabel(cell.spec)}
      styles={s}
      keyHeight={keyHeight}
    />
  );
}

function KeyBtn({
  label,
  testID,
  onPress,
  accessibilityLabel,
  styles: s,
  keyHeight = KEY_HEIGHT_MIN,
  danger,
  children,
}: {
  label?: string;
  testID: string;
  onPress: () => void;
  accessibilityLabel?: string;
  styles: PadStyles;
  keyHeight?: number;
  danger?: boolean;
  children?: ReactNode;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        s.key,
        { height: keyHeight, minHeight: keyHeight },
        pressed && s.pressed,
      ]}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? label}
      testID={testID}
    >
      {children ?? <Text style={[s.label, danger && s.labelDanger]}>{label}</Text>}
    </Pressable>
  );
}

const makeStyles = (theme: Theme) =>
  StyleSheet.create({
    pad: {
      marginTop: Space.xs,
      marginHorizontal: -12,
      paddingHorizontal: Space.xs,
      paddingTop: Space.xs,
      paddingBottom: Space.sm,
      backgroundColor: theme.surfaceAlt,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: theme.border,
      overflow: "hidden",
      gap: 6,
    },
    keys: {
      flex: 1,
      justifyContent: "flex-start",
      gap: 6,
      overflow: "hidden",
    },
    tabs: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xxs,
    },
    tabRow: { flexDirection: "row", alignItems: "center", gap: Space.xxs, paddingRight: Space.xxs },
    tab: {
      paddingHorizontal: 6,
      minHeight: Space.minTouch,
      justifyContent: "center",
      borderRadius: Radius.xs,
    },
    tabSelected: { backgroundColor: theme.primaryLight },
    tabLabel: { fontSize: 13, fontWeight: "600", color: theme.textSecondary },
    tabLabelSelected: { color: theme.primary },
    nav: { marginLeft: "auto", flexDirection: "row", alignItems: "center" },
    pasteBtn: {
      minWidth: Space.minTouch,
      minHeight: Space.minTouch,
      alignItems: "center",
      justifyContent: "center",
    },
    abc: {
      minHeight: Space.minTouch,
      justifyContent: "center",
      paddingHorizontal: 10,
    },
    abcLabel: { fontSize: 15, fontWeight: "700", color: theme.primary },
    numpad: { gap: 6 },
    keySpacer: { flex: 1 },
    row: {
      flexDirection: "row",
      alignItems: "stretch",
      gap: 6,
    },
    key: {
      flex: 1,
      minHeight: Space.minTouch,
      borderRadius: Radius.xs,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: theme.bg,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    pressed: { opacity: 0.55, transform: [{ scale: 0.97 }] },
    label: {
      fontSize: 17,
      fontWeight: "600",
      color: theme.text,
    },
    labelDanger: { color: theme.danger },
  });
