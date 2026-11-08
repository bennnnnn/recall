import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { type LayoutRectangle, Pressable, ScrollView, type ScrollViewInstance, StyleSheet, Text } from "react-native";
import { useTranslation } from "react-i18next";

import { useReduceMotion } from "@/lib/motion";
import { Radius } from "@/lib/radius";
import { SCANNER_SUBJECTS, type ScannerSubject } from "@/lib/scanner/subjects";
import { Space } from "@/lib/space";
import { Theme, useTheme, withAlpha } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";

type Props = {
  value: ScannerSubject;
  onChange: (subject: ScannerSubject) => void;
};

const LABEL_KEYS: Record<ScannerSubject, string> = {
  math: "chat.math_scan_subject_math",
  physics: "chat.math_scan_subject_physics",
  chemistry: "chat.math_scan_subject_chemistry",
  biology: "chat.math_scan_subject_biology",
};

/**
 * The subject tabs, each as wide as its name on one line ("Chemistry" wrapped to
 * "Chemistr/y" in four equal slots). A row wider than the screen scrolls sideways, and
 * the chosen tab scrolls into view.
 */
export function ScannerSubjectSwitcher({ value, onChange }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const reduceMotion = useReduceMotion();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const scrollRef = useRef<ScrollViewInstance>(null);
  const tabsRef = useRef(new Map<ScannerSubject, LayoutRectangle>());
  const [rowWidth, setRowWidth] = useState(0);

  const reveal = useCallback((subject: ScannerSubject) => {
    const tab = tabsRef.current.get(subject);
    if (!tab || rowWidth <= 0) return;
    scrollRef.current?.scrollTo({ x: Math.max(0, tab.x - (rowWidth - tab.width) / 2), animated: !reduceMotion });
  }, [reduceMotion, rowWidth]);

  useEffect(() => {
    reveal(value);
  }, [reveal, value]);

  return (
    <ScrollView
      ref={scrollRef}
      horizontal
      showsHorizontalScrollIndicator={false}
      keyboardShouldPersistTaps="handled"
      testID="scanner-subject-switcher"
      accessibilityRole="tablist"
      accessibilityLabel={t("chat.math_scan_subject_a11y")}
      style={s.row}
      contentContainerStyle={s.content}
      onLayout={(event) => setRowWidth(event.nativeEvent.layout.width)}
    >
      {SCANNER_SUBJECTS.map((subject) => {
        const selected = subject === value;
        return (
          <Pressable
            key={subject}
            testID={`scanner-subject-${subject}`}
            style={[s.tab, selected ? s.tabSelected : null]}
            // A 36 pt pill in a row padded 4 pt above and below: the row's edge is the 44 pt
            // target's (a scroll view takes no touch outside itself on Android).
            hitSlop={{ top: Space.xxs, bottom: Space.xxs }}
            onPress={() => {
              if (!selected) onChange(subject);
            }}
            onLayout={(event) => {
              tabsRef.current.set(subject, event.nativeEvent.layout);
              if (selected) reveal(subject);
            }}
            accessibilityRole="tab"
            accessibilityState={{ selected }}
            accessibilityLabel={t(LABEL_KEYS[subject])}
          >
            <Text style={[s.label, selected ? s.labelSelected : null]} numberOfLines={1}>
              {t(LABEL_KEYS[subject])}
            </Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    row: {
      flexGrow: 0,
      alignSelf: "stretch",
    },
    // Centred while the tabs fit; past the edges, the row scrolls.
    content: {
      flexGrow: 1,
      justifyContent: "center",
      alignItems: "center",
      gap: Space.xs,
      paddingHorizontal: Space.md,
      paddingVertical: Space.xxs,
    },
    // Grows with the reader's text size: a fixed height clipped the label at large text.
    tab: {
      minHeight: Space.minTouch - Space.xs,
      paddingHorizontal: Space.md,
      paddingVertical: Space.xxs,
      borderRadius: Radius.full,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: withAlpha(theme.mediaScrim, 0.55),
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: withAlpha(theme.onMedia, 0.24),
    },
    tabSelected: {
      backgroundColor: withAlpha(theme.onMedia, 0.96),
      borderColor: theme.onMedia,
    },
    label: {
      ...Type.compact,
      color: withAlpha(theme.onMedia, 0.86),
      ...Weight.bold,
    },
    labelSelected: {
      color: theme.mediaScrim,
    },
  });
}
