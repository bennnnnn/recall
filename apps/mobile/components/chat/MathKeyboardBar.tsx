import { memo, useMemo, useState, type ReactNode } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { Icon } from "@/components/Icon";
import { useTranslation } from "react-i18next";

import { MathConverterPad } from "@/components/chat/MathConverterPad";
import { selection as hapticSelection } from "@/lib/haptics";
import {
  MATH_KEYBOARD_GROUPS,
  MATH_KEYBOARD_SYMBOLS,
  MATH_NUMPAD_ROWS,
  mathGroupCanToggleDigits,
  mathGroupShowsNumpad,
  symbolA11yLabel,
  symbolRowsForGroup,
  type MathKeyboardGroup,
  type MathKeyboardSymbol,
  type PadCell,
} from "@/lib/mathKeyboardSymbols";
import { Theme, useTheme } from "@/lib/theme";

export const MATH_KEYBOARD_PAD_HEIGHT = 320;

const PAD_PADDING_V = 20;
const PAD_GAP = 6;
const KEY_HEIGHT_MIN = 42;
const KEY_HEIGHT_MAX = 72;

function fillKeyHeight(padHeight: number, tabHeight: number, keyRows: number): number {
  const gaps = keyRows * PAD_GAP;
  const inner = padHeight - PAD_PADDING_V - tabHeight - gaps;
  return Math.min(KEY_HEIGHT_MAX, Math.max(KEY_HEIGHT_MIN, Math.floor(inner / keyRows)));
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
  onNextSlot: () => void;
  onPrevSlot: () => void;
  onStepCaret: (dir: -1 | 1) => void;
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
  onNextSlot,
  onPrevSlot,
  onStepCaret,
  group,
  onGroupChange,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [digitsOpen, setDigitsOpen] = useState(false);
  const [tabHeight, setTabHeight] = useState(36);
  const canToggleDigits = mathGroupCanToggleDigits(group);
  const showNumpad = mathGroupShowsNumpad(group) || (canToggleDigits && digitsOpen);
  const fnRows = useMemo(() => symbolRowsForGroup(group), [group]);
  const digitsKeyRows = MATH_NUMPAD_ROWS.length + 1;
  const keyHeight = digitsOpen
    ? fillKeyHeight(height, tabHeight, digitsKeyRows)
    : KEY_HEIGHT_MIN;
  const trigFill = useMemo(
    () => ({
      theta: MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "trig-theta")!,
      pi: MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "trig-pi")!,
    }),
    [],
  );
  const changeGroup = (next: MathKeyboardGroup) => {
    if (!mathGroupCanToggleDigits(next)) setDigitsOpen(false);
    onGroupChange(next);
  };
  const padNav = {
    onInsert,
    onBackspace,
    onNextSlot,
    onPrevSlot,
    backspaceLabel: t("chat.math_keyboard_backspace"),
    nextLabel: t("chat.math_keyboard_next_slot"),
    prevLabel: t("chat.math_keyboard_prev_slot"),
    theme,
    styles: s,
    keyHeight,
  };

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
            onStepCaret(-1);
          }}
          style={({ pressed }) => [s.caretBtn, pressed && s.pressed]}
          accessibilityRole="button"
          accessibilityLabel={t("chat.math_keyboard_caret_left")}
          testID="math-key-caret-left"
        >
          <Icon name="chevron-back" size={18} color={theme.primary} />
        </Pressable>
        <Pressable
          onPress={() => {
            buzz();
            onStepCaret(1);
          }}
          style={({ pressed }) => [s.caretBtn, pressed && s.pressed]}
          accessibilityRole="button"
          accessibilityLabel={t("chat.math_keyboard_caret_right")}
          testID="math-key-caret-right"
        >
          <Icon name="chevron-forward" size={18} color={theme.primary} />
        </Pressable>
        <Pressable
          onPress={() => {
            buzz();
            onPaste();
          }}
          style={({ pressed }) => [s.caretBtn, pressed && s.pressed]}
          accessibilityRole="button"
          accessibilityLabel={t("chat.math_keyboard_paste")}
          testID="math-keyboard-paste"
        >
          <Icon name="clipboard-outline" size={18} color={theme.primary} />
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
      {group === "converter" ? (
        <MathConverterPad
          onAsk={onAsk}
          onStop={onStop}
          streaming={streaming}
          onInsert={onInsert}
        />
      ) : (
        <>
      {canToggleDigits && digitsOpen
        ? null
        : fnRows.map((row, r) =>
        row.length === 0 ? null : (
          <View key={r} style={s.row}>
            {row.map((cell, c) => (
              <PadKey key={`${r}-${c}`} cell={cell} {...padNav} />
            ))}
          </View>
        ),
      )}
      {showNumpad ? (
        <View style={s.numpad} testID="math-keyboard-numpad">
          {MATH_NUMPAD_ROWS.map((row, r) => (
            <View key={r} style={s.row}>
              {row.map((cell, c) => (
                <PadKey key={`${r}-${c}`} cell={cell} {...padNav} />
              ))}
            </View>
          ))}
        </View>
      ) : null}
      {canToggleDigits ? (
        <View style={s.row}>
          <KeyBtn
            label={
              digitsOpen ? t(`chat.math_keyboard_group_${group}`) : t("chat.math_keyboard_123")
            }
            testID="math-keyboard-123"
            onPress={() => {
              buzz();
              setDigitsOpen((open) => !open);
            }}
            accessibilityLabel={
              digitsOpen ? t(`chat.math_keyboard_group_${group}`) : t("chat.math_keyboard_123")
            }
            styles={s}
            keyHeight={keyHeight}
            accent
          />
          {digitsOpen ? (
            group === "trig" ? (
              <>
                <PadKey
                  cell={{ kind: "insert", spec: trigFill.theta }}
                  {...padNav}
                />
                <PadKey
                  cell={{ kind: "insert", spec: trigFill.pi }}
                  {...padNav}
                />
              </>
            ) : null
          ) : (
            <>
              <PadKey cell={{ kind: "backspace" }} {...padNav} />
              <PadKey cell={{ kind: "prev" }} {...padNav} />
              <PadKey cell={{ kind: "next" }} {...padNav} />
            </>
          )}
        </View>
      ) : null}
        </>
      )}
    </View>
  );
});

type PadStyles = ReturnType<typeof makeStyles>;

function PadKey({
  cell,
  onInsert,
  onBackspace,
  onNextSlot,
  onPrevSlot,
  backspaceLabel,
  nextLabel,
  prevLabel,
  theme,
  styles: s,
  keyHeight = KEY_HEIGHT_MIN,
}: {
  cell: PadCell;
  onInsert: (spec: MathKeyboardSymbol) => void;
  onBackspace: () => void;
  onNextSlot: () => void;
  onPrevSlot: () => void;
  backspaceLabel: string;
  nextLabel: string;
  prevLabel: string;
  theme: Theme;
  styles: PadStyles;
  keyHeight?: number;
}) {
  if (cell.kind === "spacer") {
    return <View style={s.keySpacer} />;
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
        accent
      >
        <Icon name="backspace-outline" size={20} color={theme.text} />
      </KeyBtn>
    );
  }
  if (cell.kind === "prev") {
    return (
      <KeyBtn
        label="↑"
        testID="math-key-prev-slot"
        onPress={() => {
          buzz();
          onPrevSlot();
        }}
        accessibilityLabel={prevLabel}
        styles={s}
        keyHeight={keyHeight}
        accent
      />
    );
  }
  if (cell.kind === "next") {
    return (
      <KeyBtn
        label="↓"
        testID="math-key-next-slot"
        onPress={() => {
          buzz();
          onNextSlot();
        }}
        accessibilityLabel={nextLabel}
        styles={s}
        keyHeight={keyHeight}
        accent
      />
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
  accent,
  children,
}: {
  label?: string;
  testID: string;
  onPress: () => void;
  accessibilityLabel?: string;
  styles: PadStyles;
  keyHeight?: number;
  accent?: boolean;
  children?: ReactNode;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        s.key,
        { height: keyHeight },
        accent && s.keyAccent,
        pressed && s.pressed,
      ]}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? label}
      testID={testID}
    >
      {children ?? <Text style={s.label}>{label}</Text>}
    </Pressable>
  );
}

const makeStyles = (theme: Theme) =>
  StyleSheet.create({
    pad: {
      marginTop: 8,
      marginHorizontal: -12,
      paddingHorizontal: 8,
      paddingTop: 8,
      paddingBottom: 12,
      backgroundColor: theme.surfaceAlt,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: theme.border,
      justifyContent: "flex-start",
      gap: 6,
    },
    tabs: {
      flexDirection: "row",
      alignItems: "center",
      gap: 4,
    },
    tabRow: { flexDirection: "row", alignItems: "center", gap: 4, paddingRight: 4 },
    tab: {
      paddingHorizontal: 6,
      paddingVertical: 4,
      borderRadius: 8,
    },
    tabSelected: { backgroundColor: theme.primaryLight },
    tabLabel: { fontSize: 13, fontWeight: "600", color: theme.textSecondary },
    tabLabelSelected: { color: theme.primary },
    nav: { marginLeft: "auto", flexDirection: "row", alignItems: "center" },
    caretBtn: { paddingHorizontal: 4, paddingVertical: 4 },
    abc: { paddingHorizontal: 10, paddingVertical: 4 },
    abcLabel: { fontSize: 15, fontWeight: "700", color: theme.primary },
    numpad: { gap: 6, marginTop: 2 },
    keySpacer: { flex: 1 },
    row: {
      flexDirection: "row",
      alignItems: "stretch",
      gap: 6,
    },
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
    pressed: { opacity: 0.55, transform: [{ scale: 0.97 }] },
    label: {
      fontSize: 17,
      fontWeight: "600",
      color: theme.text,
    },
  });
