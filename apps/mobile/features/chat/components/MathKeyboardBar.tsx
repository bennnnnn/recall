import { memo, useMemo } from "react";
import { StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";
import { useTranslation } from "react-i18next";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { FadingHorizontalScroll } from "@/components/markdown/FadingHorizontalScroll";
import { MathConverterPad } from "@/features/chat/components/MathConverterPad";
import { MathKey } from "@/features/chat/components/MathKey";
import { CHAT_COMPOSER_MIN_BOTTOM_PAD } from "@/features/chat/model/composerLogic";
import { selection as hapticSelection } from "@/lib/haptics";
import { PAD_GAP, TAB_ROW_HEIGHT, padKeyHeight } from "@/lib/math/keyboardPad";
import {
  MATH_KEYBOARD_GROUPS,
  padRows,
  symbolA11yLabel,
  type MathKeyboardGroup,
  type MathKeyboardSymbol,
  type PadCell,
  type SymbolPage,
} from "@/lib/math/keyboardSymbols";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Button } from "@/ui/controls/Button";
import { Chip } from "@/ui/controls/Chip";
import { IconButton } from "@/ui/controls/IconButton";
import { IconSize } from "@/ui/icons/sizes";

type Props = {
  open: boolean;
  height: number;
  onToggle: () => void;
  onInsert: (spec: MathKeyboardSymbol) => void;
  onCaret: (direction: "left" | "right") => void;
  onAsk: (text: string) => void;
  onStop: () => void;
  streaming: boolean;
  onBackspace: () => void;
  onPaste: () => void;
  group: MathKeyboardGroup;
  onGroupChange: (group: MathKeyboardGroup) => void;
};

/** How far past the composer's bottom strip the pad's ground runs: off screen, never seen. */
const GROUND_OVERRUN = Space.lg;

/**
 * The pad's key size and its frame. Its ground runs on through the composer's strip under it
 * (the home indicator) and past the screen's bottom edge, as the system keyboard's does, so
 * no message shows under the keys (2026-11-07); the keys keep their place.
 */
function usePadLayout(height: number): { keyHeight: number; frame: ViewStyle } {
  const below = Math.max(useSafeAreaInsets().bottom, CHAT_COMPOSER_MIN_BOTTOM_PAD) + GROUND_OVERRUN;
  return {
    keyHeight: padKeyHeight(height),
    frame: { height: height + below, marginBottom: -below, paddingBottom: Space.sm + below },
  };
}

export const MathKeyboardBar = memo(function MathKeyboardBar({
  open,
  height,
  onToggle,
  onInsert,
  onCaret,
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
  const { keyHeight, frame } = usePadLayout(height);
  const page: SymbolPage = group === "converter" || group === "pad" ? "basics" : group;
  const rows = useMemo(() => padRows(page), [page]);

  if (!open) return null;

  const cellKey = (cell: PadCell, at: string) => {
    if (cell.kind === "insert") {
      return (
        <MathKey
          key={at}
          label={cell.spec.label}
          testID={`math-key-${cell.spec.id}`}
          accessibilityLabel={symbolA11yLabel(cell.spec)}
          onPress={() => {
            hapticSelection();
            onInsert(cell.spec);
          }}
          height={keyHeight}
        />
      );
    }
    if (cell.kind === "backspace") {
      return (
        <MathKey
          key={at}
          icon="backspace"
          testID="math-key-backspace"
          accessibilityLabel={t("chat.math_keyboard_backspace")}
          onPress={() => {
            hapticSelection();
            onBackspace();
          }}
          height={keyHeight}
        />
      );
    }
    const direction = cell.kind;
    return (
      <MathKey
        key={at}
        icon={direction === "left" ? "caret-left" : "caret-right"}
        testID={`math-key-${direction}`}
        accessibilityLabel={t(`chat.math_keyboard_${direction}`)}
        onPress={() => {
          hapticSelection();
          onCaret(direction);
        }}
        height={keyHeight}
      />
    );
  };

  return (
    <View
      style={[s.pad, frame]}
      accessibilityLabel={t("chat.math_keyboard_a11y")}
      testID="math-keyboard-pad"
    >
      <View style={s.tabs}>
        <GroupTabs group={group} onGroupChange={onGroupChange} style={s.tabScroll} contentStyle={s.tabRow} />
        <IconButton
          name="clipboard"
          size={IconSize.sm}
          color={theme.primary}
          onPress={() => {
            hapticSelection();
            onPaste();
          }}
          accessibilityLabel={t("chat.math_keyboard_paste")}
          testID="math-keyboard-paste"
        />
        <Button
          title={t("chat.math_keyboard_abc")}
          variant="ghost"
          size="sm"
          onPress={onToggle}
          accessibilityLabel={t("chat.math_keyboard_abc")}
          testID="math-keyboard-abc"
        />
      </View>
      <View style={s.keys}>
        {group === "converter" ? (
          <MathConverterPad
            keyHeight={keyHeight}
            onAsk={onAsk}
            onStop={onStop}
            streaming={streaming}
          />
        ) : (
          rows.map((row, r) => (
            <View key={r} style={s.row}>
              {row.map((cell, c) => cellKey(cell, `${r}-${c}`))}
            </View>
          ))
        )}
      </View>
    </View>
  );
});

/** The pad's groups (Basics, Algebra, Greek…): a row of tabs over the keys, faded where more scroll. */
function GroupTabs({
  group,
  onGroupChange,
  style,
  contentStyle,
}: {
  group: MathKeyboardGroup;
  onGroupChange: (group: MathKeyboardGroup) => void;
  style: StyleProp<ViewStyle>;
  contentStyle: StyleProp<ViewStyle>;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <FadingHorizontalScroll
      testID="math-keyboard-tabs"
      fadeColor={theme.surfaceAlt}
      style={style}
      contentContainerStyle={contentStyle}
      accessibilityRole="tablist"
    >
      {MATH_KEYBOARD_GROUPS.map((id) => (
        <Chip
          key={id}
          label={t(`chat.math_keyboard_group_${id}`)}
          selected={id === group}
          onPress={() => onGroupChange(id)}
          accessibilityRole="tab"
          testID={`math-keyboard-tab-${id}`}
        />
      ))}
    </FadingHorizontalScroll>
  );
}

const makeStyles = (theme: Theme) =>
  StyleSheet.create({
    pad: {
      marginTop: Space.xs,
      // Edge to edge, as the system keyboard is: this cancels the composer's own side gutter.
      marginHorizontal: -Space.md,
      paddingHorizontal: Space.xs,
      paddingTop: Space.xs,
      paddingBottom: Space.sm,
      backgroundColor: theme.surfaceAlt,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: theme.border,
      overflow: "hidden",
      gap: PAD_GAP,
    },
    tabs: {
      height: TAB_ROW_HEIGHT,
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xxs,
    },
    // The tabs run on behind Paste and ABC: the cut edge fades, so the last ones read as more.
    tabScroll: { flex: 1 },
    tabRow: { flexDirection: "row", alignItems: "center", gap: Space.xxs, paddingRight: Space.xxs },
    keys: { flex: 1, gap: PAD_GAP },
    row: { flexDirection: "row", gap: PAD_GAP },
  });
