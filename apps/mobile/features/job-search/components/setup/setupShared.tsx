import { useMemo } from "react";
import { StyleSheet, Text } from "react-native";

import type {
  JobSearchExperience,
  JobSearchFrequency,
  JobSearchWorkMode,
} from "@/lib/api";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Chip } from "@/ui/controls/Chip";
import { Type, Weight } from "@/lib/type";

export const WORK_MODE_VALUES: JobSearchWorkMode[] = ["remote", "hybrid", "onsite"];
export const EXPERIENCE_VALUES: JobSearchExperience[] = [
  "internship",
  "entry",
  "mid",
  "senior",
];
export const FREQUENCY_VALUES: JobSearchFrequency[] = [
  "daily",
  "weekdays",
  "weekly",
  "monthly",
];

/** Backend caps (JobSearchUpsert): target_roles ≤ 6, skills ≤ 30. */
export const MAX_ROLES = 6;
export const MAX_SKILLS = 30;

export function toggleSelection<T extends string>(value: T, values: T[]): T[] {
  if (values.includes(value)) {
    return values.length > 1 ? values.filter((item) => item !== value) : values;
  }
  return [...values, value];
}

export function nextMorning(): Date {
  const value = new Date();
  value.setDate(value.getDate() + 1);
  value.setHours(8, 0, 0, 0);
  return value;
}

export function usableRunDate(value: string | undefined): Date {
  if (!value) return nextMorning();
  const parsed = new Date(value);
  if (!Number.isFinite(parsed.getTime()) || parsed.getTime() <= Date.now()) {
    return nextMorning();
  }
  return parsed;
}

export function formatRunDate(value: Date): string {
  return value.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function SelectChip<T extends string>({
  value,
  label,
  selected,
  onPress,
  disabled,
}: {
  value: T;
  label: string;
  selected: boolean;
  onPress: (value: T) => void;
  disabled?: boolean;
}) {
  return (
    <Chip
      variant="filter"
      label={label}
      selected={selected}
      disabled={disabled}
      onPress={() => onPress(value)}
    />
  );
}

export function FieldLabel({ children }: { children: string }) {
  const s = useSetupStyles();
  return <Text style={s.label}>{children}</Text>;
}

export function useSetupStyles() {
  const C = useTheme();
  return useMemo(() => makeStyles(C), [C]);
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    screen: {
      flex: 1,
      backgroundColor: C.bg,
    },
    flex: { flex: 1 },
    scrollContent: { flexGrow: 1 },
    footer: {
      paddingHorizontal: Space.lg,
      paddingTop: Space.xs,
      paddingBottom: Space.md,
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      paddingHorizontal: Space.md,
      paddingTop: Space.sm,
      gap: Space.sm,
    },
    headerSide: { minWidth: 64, minHeight: 44, justifyContent: "center" },
    headerCancel: { ...Type.body, color: C.textSecondary },
    headerTitle: {
      ...Type.navTitle,
      color: C.text,
      flex: 1,
      textAlign: "center",
    },
    body: {
      paddingHorizontal: Space.lg,
      paddingTop: Space.lg,
      paddingBottom: Space.xl,
      gap: Space.lg,
    },
    intro: { gap: Space.xs },
    progressWrap: {
      paddingHorizontal: Space.lg,
      paddingTop: Space.sm,
      gap: Space.xs,
    },
    progressRow: { flexDirection: "row", gap: Space.xs },
    progressSegment: {
      flex: 1,
      height: 4,
      borderRadius: 2,
      backgroundColor: C.surfaceAlt,
    },
    progressSegmentActive: { backgroundColor: C.primary },
    progressText: { ...Type.caption, color: C.textTertiary, textAlign: "right" },
    title: {
      ...Type.display,
      lineHeight: 32,
      color: C.text,
    },
    subtitle: { ...Type.body, color: C.textSecondary },
    fieldGroup: { gap: Space.xs },
    label: { ...Type.label, color: C.text },
    input: {
      ...Type.body,
      minHeight: 54,
      borderRadius: Radius.xl,
      backgroundColor: C.surface,
      color: C.text,
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
    },
    inputError: { borderColor: C.danger },
    selectRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      minHeight: 54,
      borderRadius: Radius.xl,
      backgroundColor: C.surface,
      paddingHorizontal: Space.md,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
    },
    selectValue: { ...Type.body, color: C.text, flex: 1 },
    errorText: { ...Type.caption, color: C.danger },
    helper: { ...Type.caption, color: C.textTertiary },
    chipRow: {
      flexDirection: "row",
      flexWrap: "wrap",
      gap: Space.xs,
    },
    resumeCard: {
      minHeight: 72,
      borderRadius: Radius.xl,
      backgroundColor: C.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
    },
    resumeIcon: {
      width: 44,
      height: 44,
      borderRadius: Radius.md,
      backgroundColor: C.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    resumeCopy: { flex: 1, gap: 2 },
    resumeTitle: { ...Type.label, color: C.text },
    resumeMeta: { ...Type.caption, color: C.textTertiary },
    removeResume: { alignSelf: "flex-start", paddingVertical: Space.xxs },
    removeResumeText: { ...Type.secondary, ...Weight.semibold, color: C.danger },
    twoColumnRow: { flexDirection: "row", gap: Space.sm },
    flexField: { flex: 1, gap: Space.xs },
    dateCard: {
      minHeight: 72,
      borderRadius: Radius.xl,
      backgroundColor: C.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
    },
    reviewCard: {
      borderRadius: Radius.xl,
      backgroundColor: C.primaryLight,
      padding: Space.md,
      gap: Space.xs,
    },
    reviewTitle: { ...Type.label, color: C.text, marginBottom: Space.xxs },
    reviewRow: { flexDirection: "row", alignItems: "flex-start", gap: Space.xs },
    reviewText: { ...Type.secondary, color: C.textSecondary, flex: 1 },
    dateIcon: {
      width: 44,
      height: 44,
      borderRadius: Radius.md,
      backgroundColor: C.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    dateCopy: { flex: 1, gap: 2 },
    dateTitle: { ...Type.label, color: C.text },
    dateMeta: { ...Type.caption, color: C.textTertiary },
    primaryButton: {
      minHeight: 56,
      borderRadius: Radius.full,
      backgroundColor: C.primary,
      alignItems: "center",
      justifyContent: "center",
      marginTop: Space.xs,
    },
    primaryButtonText: { ...Type.body, ...Weight.bold, color: C.onPrimary },
    pressed: { opacity: 0.72 },
    disabled: { opacity: 0.45 },
  });
}
