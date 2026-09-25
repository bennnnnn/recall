import { useMemo, useState, type ReactNode } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { useTranslation } from "react-i18next";
import type { Memory } from "@/lib/api";
import { MEMORY_TEXT_MAX_LENGTH } from "@/features/memory/model/memoryFacts";
import { MESSAGE_FOLD_MAX_HEIGHT } from "@/lib/markdown/messageFold";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Type } from "@/lib/type";
import { useTheme, withAlpha, type Theme } from "@/lib/theme";

function memoryTypeLabel(type: string, t: (key: string) => string): string {
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
      <Text style={s.groupTitle}>{memoryTypeLabel(type, t)}</Text>
    </View>
  );
}

/** One fact. The page owns the single edit control; this row only shows the text or the field. */
export function MemoryFactRow({
  fact,
  pending,
  first,
  last,
  editing,
  draftText,
  draftTooLong,
  onChangeDraft,
}: {
  fact: Memory;
  pending: boolean;
  first: boolean;
  last: boolean;
  editing: boolean;
  draftText: string;
  draftTooLong: boolean;
  onChangeDraft: (text: string) => void;
}) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { t } = useTranslation();

  return (
    <View
      style={[
        s.factRow,
        first ? null : s.factRowDivider,
        last ? s.factRowLast : null,
        editing ? s.factRowEditing : null,
      ]}
    >
      {editing ? (
        <View style={s.inlineEditor}>
          <TextInput
            style={[s.inlineInput, draftTooLong ? s.inlineInputError : null]}
            accessibilityLabel={fact.text}
            value={draftText}
            onChangeText={onChangeDraft}
            multiline
            editable={!pending}
            textAlignVertical="top"
          />
          <Text style={[s.counter, draftTooLong ? s.counterOver : null]}>
            {t("memory.edit_count", {
              count: Array.from(draftText).length,
              max: MEMORY_TEXT_MAX_LENGTH,
            })}
          </Text>
        </View>
      ) : (
        <Text style={s.factText}>{fact.text}</Text>
      )}
    </View>
  );
}

/** Fold the whole memory card the way a long message folds, then expand all of it. */
export function MemoryFold({
  children,
  editing,
  fadeColor,
}: {
  children: ReactNode;
  editing: boolean;
  fadeColor: string;
}) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { t } = useTranslation();
  const [height, setHeight] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const needsFold = height > MESSAGE_FOLD_MAX_HEIGHT;
  const folded = needsFold && !expanded && !editing;

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
      {needsFold && !editing ? (
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
    factRowEditing: {
      paddingVertical: Space.sm,
    },
    inlineEditor: { flex: 1 },
    inlineInput: {
      minHeight: 76,
      maxHeight: 180,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      borderRadius: Radius.md,
      paddingHorizontal: Space.sm,
      paddingVertical: Space.sm,
      ...Type.body,
      color: theme.text,
      backgroundColor: theme.bg,
    },
    inlineInputError: { borderColor: theme.danger },
    counter: { ...Type.meta, color: theme.textTertiary, marginTop: 2 },
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
