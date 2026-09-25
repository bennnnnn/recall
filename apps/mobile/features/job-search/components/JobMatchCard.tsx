import { useMemo } from "react";
import { Alert, Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/ui/icons/Icon";
import { CompanyLogo } from "@/features/job-search/components/CompanyLogo";
import { JobFitBadge } from "@/features/job-search/components/JobFitBadge";
import { JobMatchMetaChips } from "@/features/job-search/components/JobMatchMetaChips";
import { JobMatchReasons } from "@/features/job-search/components/JobMatchReasons";
import { StatusPill } from "@/ui/feedback/StatusPill";
import type { JobMatch, JobMatchStatus } from "@/lib/api";
import { canToggleApplied, hasApplied } from "@/features/job-search/model/stages";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

function Action({
  icon,
  label,
  active,
  primary,
  disabled,
  onPress,
}: {
  icon: "bookmark-outline" | "bookmark" | "checkmark-circle-outline" | "open-outline";
  label: string;
  active?: boolean;
  primary?: boolean;
  disabled?: boolean;
  onPress: () => void;
}) {
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const iconColor = primary ? C.primary : active ? C.primary : C.textSecondary;
  return (
    <Pressable
      style={({ pressed }) => [
        s.action,
        primary && s.actionPrimary,
        active && !primary && s.actionActive,
        pressed && s.pressed,
      ]}
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityState={{ selected: !!active, disabled: !!disabled }}
    >
      <Icon name={icon} size={18} color={iconColor} />
      <Text
        style={[
          s.actionText,
          primary && s.actionTextPrimary,
          active && !primary && s.actionTextActive,
        ]}
      >
        {label}
      </Text>
    </Pressable>
  );
}

export function JobMatchCard({
  match,
  onStatus,
  onSavedChange,
  onPress,
}: {
  match: JobMatch;
  onStatus: (status: JobMatchStatus) => void;
  onSavedChange: (saved: boolean) => void;
  onPress?: () => void;
}) {
  const C = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(C), [C]);
  const applicationStarted = hasApplied(match.status);

  const openJob = async () => {
    try {
      await Linking.openURL(match.url);
    } catch {
      Alert.alert(t("my_job.open_failed_title"), t("my_job.open_failed_body"));
    }
  };

  return (
    <View style={s.card}>
      <Pressable
        style={({ pressed }) => [s.cardLink, pressed && onPress != null && s.pressed]}
        onPress={onPress}
        disabled={onPress == null}
        accessibilityRole={onPress != null ? "button" : undefined}
      >
        <View style={s.headingRow}>
          <CompanyLogo company={match.company} uri={match.company_logo_url} />
          <View style={s.headingCopy}>
            <Text style={s.title} numberOfLines={2}>{match.title}</Text>
            <View style={s.companyRow}>
              <Text style={s.company}>{match.company}</Text>
              {match.status === "interviewing" ||
              match.status === "offer" ||
              match.status === "rejected" ? (
                <StatusPill
                  label={t(`my_job.stage_${match.status}`)}
                  tone={
                    match.status === "offer"
                      ? "success"
                      : match.status === "rejected"
                        ? "neutral"
                        : "accent"
                  }
                />
              ) : null}
            </View>
          </View>
          <JobFitBadge score={match.match_score} />
        </View>
        <JobMatchMetaChips match={match} />
      </Pressable>
      <JobMatchReasons match={match} maxReasons={3} />

      <View style={s.divider} />
      <View style={s.actions}>
        <Action icon="open-outline" label={t("my_job.view_job")} primary onPress={() => void openJob()} />
        <Action
          icon={match.is_saved ? "bookmark" : "bookmark-outline"}
          label={match.is_saved ? t("my_job.saved") : t("my_job.save")}
          active={match.is_saved}
          onPress={() => onSavedChange(!match.is_saved)}
        />
        <Action
          icon="checkmark-circle-outline"
          label={applicationStarted ? t("my_job.applied") : t("my_job.i_applied")}
          active={applicationStarted}
          disabled={!canToggleApplied(match.status)}
          onPress={() => onStatus(match.status === "applied" ? "new" : "applied")}
        />
      </View>
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    card: {
      backgroundColor: C.surface,
      borderRadius: Radius.composer,
      padding: Space.md,
      gap: Space.sm,
    },
    cardLink: { gap: Space.sm },
    headingRow: { flexDirection: "row", alignItems: "flex-start", gap: Space.sm },
    headingCopy: { flex: 1, minWidth: 0 },
    title: { ...Type.navTitle, color: C.text, fontWeight: "700" },
    companyRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      marginTop: 2,
    },
    company: { ...Type.secondary, color: C.textSecondary, flexShrink: 1 },
    divider: {
      height: StyleSheet.hairlineWidth,
      backgroundColor: C.border,
      marginTop: Space.xs,
    },
    actions: { flexDirection: "row", flexWrap: "wrap", gap: Space.xs },
    action: {
      minHeight: 44,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: Space.xxs,
      paddingHorizontal: Space.sm,
      borderRadius: Radius.full,
      backgroundColor: C.surfaceAlt,
    },
    actionPrimary: {
      backgroundColor: C.primaryLight,
      paddingHorizontal: Space.xs,
    },
    actionActive: { backgroundColor: C.primaryLight },
    actionText: { ...Type.compact, color: C.textSecondary, fontWeight: "600" },
    actionTextPrimary: { color: C.primary },
    actionTextActive: { color: C.primary },
    pressed: { opacity: 0.68 },
  });
}
