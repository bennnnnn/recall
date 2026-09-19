import { useMemo } from "react";
import { Alert, Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { JobMatchMetaChips, matchScoreColor } from "@/components/jobSearch/JobMatchMetaChips";
import type { JobMatch, JobMatchStatus } from "@/lib/api";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

function Action({
  icon,
  label,
  active,
  primary,
  onPress,
}: {
  icon: "bookmark-outline" | "bookmark" | "checkmark-circle-outline" | "open-outline" | "close";
  label: string;
  active?: boolean;
  primary?: boolean;
  onPress: () => void;
}) {
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const iconColor = primary ? C.onPrimary : active ? C.primary : C.textSecondary;
  return (
    <Pressable
      style={({ pressed }) => [
        s.action,
        primary && s.actionPrimary,
        active && !primary && s.actionActive,
        pressed && s.pressed,
      ]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected: !!active }}
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
  onPress,
}: {
  match: JobMatch;
  onStatus: (status: JobMatchStatus) => void;
  onPress?: () => void;
}) {
  const C = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(C), [C]);
  const initial = match.company.trim().charAt(0).toUpperCase() || "J";
  const score = match.match_score;
  const scoreColor = matchScoreColor(score, C);

  const openJob = async () => {
    try {
      await Linking.openURL(match.url);
    } catch {
      Alert.alert(t("my_job.open_failed_title"), t("my_job.open_failed_body"));
    }
  };

  return (
    <Pressable
      style={({ pressed }) => [s.card, pressed && onPress != null && s.pressed]}
      onPress={onPress}
      disabled={onPress == null}
      accessibilityRole={onPress != null ? "button" : undefined}
    >
      <View style={s.headingRow}>
        <View
          style={s.logo}
          accessibilityLabel={
            score != null ? t("my_job.match_fit", { score }) : match.company
          }
        >
          {score != null ? (
            <Text style={[s.logoText, { color: scoreColor }]}>{score}%</Text>
          ) : (
            <Text style={s.logoText}>{initial}</Text>
          )}
        </View>
        <View style={s.headingCopy}>
          <Text style={s.title}>{match.title}</Text>
          <Text style={s.company}>{match.company}</Text>
        </View>
        <Pressable
          style={({ pressed }) => [s.hideButton, pressed && s.pressed]}
          onPress={() => onStatus("hidden")}
          accessibilityRole="button"
          accessibilityLabel={t("my_job.not_interested")}
        >
          <Icon name="close" size={20} color={C.textTertiary} />
        </Pressable>
      </View>

      <JobMatchMetaChips match={match} />
      {match.summary ? <Text style={s.summary} numberOfLines={3}>{match.summary}</Text> : null}

      {match.match_reasons.length > 0 ? (
        <View style={s.reasonBlock}>
          <Text style={s.reasonTitle}>{t("my_job.why_matches")}</Text>
          {match.match_reasons.slice(0, 3).map((reason) => (
            <View key={reason} style={s.reasonRow}>
              <View style={s.reasonDot} />
              <Text style={s.reasonText}>{reason}</Text>
            </View>
          ))}
        </View>
      ) : null}

      {match.gap ? (
        <View style={s.gapRow}>
          <Icon name="information-circle-outline" size={18} color={C.textTertiary} />
          <Text style={s.gapText}>{match.gap}</Text>
        </View>
      ) : null}

      <View style={s.divider} />
      <View style={s.actions}>
        <Action icon="open-outline" label={t("my_job.view_job")} primary onPress={() => void openJob()} />
        <Action
          icon={match.status === "saved" ? "bookmark" : "bookmark-outline"}
          label={match.status === "saved" ? t("my_job.saved") : t("my_job.save")}
          active={match.status === "saved"}
          onPress={() => onStatus(match.status === "saved" ? "new" : "saved")}
        />
        <Action
          icon="checkmark-circle-outline"
          label={match.status === "applied" ? t("my_job.applied") : t("my_job.i_applied")}
          active={match.status === "applied"}
          onPress={() => onStatus(match.status === "applied" ? "new" : "applied")}
        />
      </View>
    </Pressable>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    card: {
      backgroundColor: C.surface,
      borderRadius: 24,
      padding: Space.md,
      gap: Space.sm,
    },
    headingRow: { flexDirection: "row", alignItems: "flex-start", gap: Space.sm },
    logo: {
      width: 48,
      height: 48,
      borderRadius: 15,
      backgroundColor: C.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    logoText: { ...Type.secondary, color: C.primary, fontWeight: "700" },
    headingCopy: { flex: 1, minWidth: 0 },
    title: { ...Type.navTitle, color: C.text, fontWeight: "700" },
    company: { ...Type.secondary, color: C.textSecondary, marginTop: 2 },
    hideButton: {
      width: 44,
      height: 44,
      borderRadius: 22,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: C.surfaceAlt,
      // Keep the card's heading row height driven by the 48px logo.
      marginVertical: -4,
      marginRight: -4,
    },
    summary: { ...Type.body, color: C.textSecondary },
    reasonBlock: {
      backgroundColor: C.contentSurface,
      borderRadius: Radius.xl,
      padding: Space.sm,
      gap: Space.xs,
    },
    reasonTitle: { ...Type.label, color: C.text },
    reasonRow: { flexDirection: "row", alignItems: "flex-start", gap: Space.xs },
    reasonDot: {
      width: 6,
      height: 6,
      borderRadius: 3,
      backgroundColor: C.primary,
      marginTop: 7,
    },
    reasonText: { ...Type.secondary, color: C.textSecondary, flex: 1 },
    gapRow: { flexDirection: "row", alignItems: "flex-start", gap: Space.xs },
    gapText: { ...Type.compact, color: C.textTertiary, flex: 1 },
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
      backgroundColor: C.primary,
      flexGrow: 1,
    },
    actionActive: { backgroundColor: C.primaryLight },
    actionText: { ...Type.compact, color: C.textSecondary, fontWeight: "600" },
    actionTextPrimary: { color: C.onPrimary },
    actionTextActive: { color: C.primary },
    pressed: { opacity: 0.68 },
  });
}
