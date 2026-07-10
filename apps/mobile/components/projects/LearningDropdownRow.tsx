import { useMemo, type ReactNode } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { Theme, useTheme } from "@/lib/theme";

type RowProps = {
  label: string;
  value: string;
  onPress?: () => void;
  disabled?: boolean;
  readOnly?: boolean;
};

export function LearningDropdownRow({
  label,
  value,
  onPress,
  disabled,
  readOnly = false,
}: RowProps) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  if (readOnly || !onPress) {
    return (
      <View style={s.row}>
        <Text style={s.label}>{label}</Text>
        <Text style={[s.value, s.valueReadOnly]} numberOfLines={2}>
          {value}
        </Text>
      </View>
    );
  }

  return (
    <Pressable
      style={[s.row, disabled && s.rowDisabled]}
      onPress={onPress}
      disabled={disabled}
    >
      <Text style={s.label}>{label}</Text>
      <View style={s.valueWrap}>
        <Text style={s.value} numberOfLines={1}>
          {value}
        </Text>
        <Ionicons name="chevron-down" size={16} color={theme.textTertiary} />
      </View>
    </Pressable>
  );
}

/** Read-only label + value row for learning summary cards. */
export function LearningSelectionRow({ label, value }: { label: string; value: string }) {
  return <LearningDropdownRow label={label} value={value} readOnly />;
}

export function LearningDropdownCard({ children }: { children: ReactNode }) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return <View style={s.card}>{children}</View>;
}

export function LearningDropdownDivider() {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return <View style={s.divider} />;
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    card: {
      borderRadius: 16,
      backgroundColor: theme.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      overflow: "hidden",
    },
    row: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingVertical: 13,
      paddingHorizontal: 16,
      gap: 12,
    },
    rowDisabled: { opacity: 0.5 },
    label: {
      flex: 1,
      fontSize: 15,
      fontWeight: "500",
      color: theme.textSecondary,
    },
    valueWrap: {
      flexDirection: "row",
      alignItems: "center",
      gap: 4,
      flexShrink: 1,
      maxWidth: "58%",
    },
    value: {
      fontSize: 15,
      fontWeight: "700",
      color: theme.text,
      textAlign: "right",
    },
    valueReadOnly: {
      flexShrink: 1,
      maxWidth: "58%",
    },
    divider: {
      height: StyleSheet.hairlineWidth,
      backgroundColor: theme.border,
      marginLeft: 16,
    },
  });
}
