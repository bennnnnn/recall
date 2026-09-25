import { useMemo, useState, type ReactNode } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { useTranslation } from "react-i18next";
import type { Memory } from "@/lib/api";
import { MESSAGE_FOLD_MAX_HEIGHT } from "@/lib/markdown/messageFold";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Type } from "@/lib/type";
import { useTheme, withAlpha, type Theme } from "@/lib/theme";

export function memorySectionLabel(type: string, t: (key: string) => string): string {
  const key = `memory.type.${type}`;
  const label = t(key);
  return label === key ? type : label;
}

/** A titled division inside the single unified memory card. */
export function MemorySectionHeader({ type, first }: { type: string; first: boolean }) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { t } = useTranslation();

  return (
    <View style={[s.groupHeader, first ? s.groupHeaderFirst : s.groupHeaderNext]}>
      <Text style={s.groupTitle}>{memorySectionLabel(type, t)}</Text>
    </View>
  );
}

/** One fact line inside the read-only page. Editing is a single field on the screen. */
export function MemoryFactRow({
  fact,
  first,
  last,
}: {
  fact: Memory;
  first: boolean;
  last: boolean;
}) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <View style={[s.factRow, first ? null : s.factRowDivider, last ? s.factRowLast : null]}>
      <Text style={s.factText}>{fact.text}</Text>
    </View>
  );
}

/** Fold the whole memory card the way a long message folds, then expand all of it. */
export function MemoryFold({
  children,
  fadeColor,
}: {
  children: ReactNode;
  fadeColor: string;
}) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { t } = useTranslation();
  const [height, setHeight] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const needsFold = height > MESSAGE_FOLD_MAX_HEIGHT;
  const folded = needsFold && !expanded;

  return (
    <View style={s.fold}>
      <View style={folded ? s.clipped : undefined}>
        <View
          testID="memory-fold-body"
          onLayout={(event) => {
            const next = event.nativeEvent.layout.height;
            setHeight((prev) => (prev === next ? prev : next));
          }}
        >
          {children}
        </View>
      </View>
      {folded && fadeColor ? (
        <LinearGradient
          colors={[withAlpha(fadeColor, 0), withAlpha(fadeColor, 0.9), fadeColor]}
          style={s.fade}
          pointerEvents="none"
        />
      ) : null}
      {needsFold ? (
        <Pressable
          style={s.toggle}
          onPress={() => setExpanded((value) => !value)}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityState={{ expanded }}
          accessibilityLabel={expanded ? t("common.show_less") : t("common.show_more")}
        >
          <Text style={s.toggleText}>
            {expanded ? t("common.show_less") : t("common.show_more")}
          </Text>
        </Pressable>
      ) : null}
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    groupHeader: {
      flexDirection: "row",
      alignItems: "center",
      paddingHorizontal: Space.md,
      paddingTop: Space.md,
      paddingBottom: Space.xs,
      backgroundColor: theme.surfaceAlt,
    },
    groupHeaderFirst: {
      borderTopLeftRadius: Radius.lg,
      borderTopRightRadius: Radius.lg,
    },
    groupHeaderNext: {
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: theme.border,
    },
    groupTitle: {
      ...Type.caption,
      fontWeight: "700",
      color: theme.text,
      textTransform: "uppercase",
      letterSpacing: 0.5,
    },
    factRow: {
      backgroundColor: theme.surfaceAlt,
      paddingHorizontal: Space.md,
      paddingVertical: Space.xs,
    },
    factRowDivider: {
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: theme.border,
    },
    factRowLast: {
      borderBottomLeftRadius: Radius.lg,
      borderBottomRightRadius: Radius.lg,
      paddingBottom: Space.md,
      marginBottom: Space.gutter,
    },
    factText: { ...Type.body, color: theme.text },
    fold: { position: "relative", alignSelf: "stretch" },
    clipped: { maxHeight: MESSAGE_FOLD_MAX_HEIGHT, overflow: "hidden" },
    fade: {
      position: "absolute",
      left: 0,
      right: 0,
      bottom: 28,
      height: 48,
    },
    toggle: {
      alignSelf: "flex-start",
      paddingVertical: Space.xxs,
      marginTop: 2,
    },
    toggleText: { ...Type.label, color: theme.primary },
  });
}
