import { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Alert, Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Icon } from "@/components/Icon";
import { JobMatchMetaChips, matchScoreColor } from "@/components/jobSearch/JobMatchMetaChips";
import { useAuth } from "@/contexts/AuthContext";
import { api, type JobMatch, type JobMatchStatus } from "@/lib/api";
import { notifyWarning, selection, tap } from "@/lib/haptics";
import { cacheJobMatch, cacheJobMatches, getCachedJobMatch } from "@/lib/jobSearch/matchCache";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

export default function JobMatchDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const { t } = useTranslation();
  const { token } = useAuth();

  const [match, setMatch] = useState<JobMatch | null>(() =>
    id ? getCachedJobMatch(id) : null,
  );
  const [loading, setLoading] = useState(match == null);

  useEffect(() => {
    if (match != null || !id || !token) return;
    let alive = true;
    // Cold start / deep link: the cache is empty, so load the dashboard once.
    void api
      .getJobSearch(token)
      .then((dashboard) => {
        if (!alive) return;
        cacheJobMatches(dashboard.matches);
        setMatch(dashboard.matches.find((item) => item.id === id) ?? null);
      })
      .catch(() => {
        if (alive) setMatch(null);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, token]);

  const openJob = useCallback(async () => {
    if (!match) return;
    try {
      await Linking.openURL(match.url);
    } catch {
      Alert.alert(t("my_job.open_failed_title"), t("my_job.open_failed_body"));
    }
  }, [match, t]);

  const updateStatus = useCallback(
    async (status: JobMatchStatus) => {
      if (!match || !token) return;
      const previous = match;
      const next = { ...match, status };
      setMatch(next);
      cacheJobMatch(next);
      try {
        await api.setJobMatchStatus(token, match.id, status);
        if (status === "hidden") router.back();
      } catch {
        setMatch(previous);
        cacheJobMatch(previous);
        Alert.alert(t("my_job.refresh_error"));
      }
    },
    [match, token, router, t],
  );

  const score = match?.match_score ?? null;
  const scoreColor = matchScoreColor(score, C);

  return (
    <View style={[s.screen, { paddingTop: insets.top }]}>
      <View style={s.header}>
        <Pressable
          style={({ pressed }) => [s.headerButton, pressed && s.pressed]}
          onPress={() => router.back()}
          accessibilityRole="button"
          accessibilityLabel={t("common.back")}
        >
          <Icon name="chevron-back" size={22} color={C.text} />
        </Pressable>
        <Text style={s.headerTitle} numberOfLines={1}>
          {match?.company ?? t("my_job.title")}
        </Text>
        <View style={s.headerButton} />
      </View>

      {loading ? (
        <View style={s.center}>
          <ActivityIndicator color={C.primary} />
        </View>
      ) : match == null ? (
        <View style={s.center}>
          <Icon name="briefcase-outline" size={40} color={C.textTertiary} />
          <Text style={s.notFound}>{t("my_job.detail_not_found")}</Text>
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
          showsVerticalScrollIndicator={false}
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
                <Text style={s.logoText}>
                  {match.company.trim().charAt(0).toUpperCase() || "J"}
                </Text>
              )}
            </View>
            <View style={s.headingCopy}>
              <Text style={s.title}>{match.title}</Text>
              <Text style={s.company}>{match.company}</Text>
            </View>
          </View>

          <JobMatchMetaChips match={match} />

          {match.summary ? <Text style={s.summary}>{match.summary}</Text> : null}

          {match.match_reasons.length > 0 ? (
            <View style={s.reasonBlock}>
              <Text style={s.sectionTitle}>{t("my_job.why_matches")}</Text>
              {match.match_reasons.map((reason) => (
                <View key={reason} style={s.reasonRow}>
                  <View style={s.reasonDot} />
                  <Text style={s.reasonText}>{reason}</Text>
                </View>
              ))}
            </View>
          ) : null}

          {match.gap ? (
            <View style={s.gapBlock}>
              <Text style={s.sectionTitle}>{t("my_job.gap_title")}</Text>
              <View style={s.reasonRow}>
                <Icon name="information-circle-outline" size={18} color={C.textTertiary} />
                <Text style={s.gapText}>{match.gap}</Text>
              </View>
            </View>
          ) : null}

          <Text style={s.source}>
            {t("my_job.source_label")}: {match.source}
          </Text>

          <View style={s.actions}>
            <Pressable
              style={({ pressed }) => [s.action, s.actionPrimary, pressed && s.pressed]}
              onPress={() => {
                tap();
                void openJob();
              }}
              accessibilityRole="button"
            >
              <Icon name="open-outline" size={18} color={C.onPrimary} />
              <Text style={[s.actionText, s.actionTextPrimary]}>{t("my_job.view_job")}</Text>
            </Pressable>
            <Pressable
              style={({ pressed }) => [
                s.action,
                match.status === "saved" && s.actionActive,
                pressed && s.pressed,
              ]}
              onPress={() => {
                selection();
                void updateStatus(match.status === "saved" ? "new" : "saved");
              }}
              accessibilityRole="button"
              accessibilityState={{ selected: match.status === "saved" }}
            >
              <Icon
                name={match.status === "saved" ? "bookmark" : "bookmark-outline"}
                size={18}
                color={match.status === "saved" ? C.primary : C.textSecondary}
              />
              <Text
                style={[s.actionText, match.status === "saved" && s.actionTextActive]}
              >
                {match.status === "saved" ? t("my_job.saved") : t("my_job.save")}
              </Text>
            </Pressable>
            <Pressable
              style={({ pressed }) => [
                s.action,
                match.status === "applied" && s.actionActive,
                pressed && s.pressed,
              ]}
              onPress={() => {
                selection();
                void updateStatus(match.status === "applied" ? "new" : "applied");
              }}
              accessibilityRole="button"
              accessibilityState={{ selected: match.status === "applied" }}
            >
              <Icon
                name="checkmark-circle-outline"
                size={18}
                color={match.status === "applied" ? C.primary : C.textSecondary}
              />
              <Text
                style={[s.actionText, match.status === "applied" && s.actionTextActive]}
              >
                {match.status === "applied" ? t("my_job.applied") : t("my_job.i_applied")}
              </Text>
            </Pressable>
            <Pressable
              style={({ pressed }) => [s.action, pressed && s.pressed]}
              onPress={() => {
                notifyWarning();
                void updateStatus("hidden");
              }}
              accessibilityRole="button"
              accessibilityLabel={t("my_job.not_interested")}
            >
              <Icon name="close" size={18} color={C.textSecondary} />
              <Text style={s.actionText}>{t("my_job.not_interested")}</Text>
            </Pressable>
          </View>
        </ScrollView>
      )}
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    screen: { flex: 1, backgroundColor: C.bg },
    header: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      paddingHorizontal: Space.sm,
      paddingVertical: Space.xs,
    },
    headerButton: {
      width: 44,
      height: 44,
      borderRadius: 22,
      alignItems: "center",
      justifyContent: "center",
    },
    headerTitle: {
      ...Type.navTitle,
      color: C.text,
      flex: 1,
      textAlign: "center",
    },
    center: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      gap: Space.sm,
      padding: Space.lg,
    },
    notFound: { ...Type.body, color: C.textSecondary, textAlign: "center" },
    content: { padding: Space.md, gap: Space.md },
    headingRow: { flexDirection: "row", alignItems: "center", gap: Space.sm },
    logo: {
      width: 56,
      height: 56,
      borderRadius: 17,
      backgroundColor: C.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    logoText: { ...Type.navTitle, color: C.primary, fontWeight: "700" },
    headingCopy: { flex: 1, minWidth: 0 },
    title: { ...Type.navTitle, color: C.text, fontWeight: "700" },
    company: { ...Type.body, color: C.textSecondary, marginTop: 2 },
    summary: { ...Type.body, color: C.textSecondary },
    sectionTitle: { ...Type.label, color: C.text },
    reasonBlock: {
      backgroundColor: C.contentSurface,
      borderRadius: Radius.xl,
      padding: Space.md,
      gap: Space.xs,
    },
    reasonRow: { flexDirection: "row", alignItems: "flex-start", gap: Space.xs },
    reasonDot: {
      width: 6,
      height: 6,
      borderRadius: 3,
      backgroundColor: C.primary,
      marginTop: 7,
    },
    reasonText: { ...Type.secondary, color: C.textSecondary, flex: 1 },
    gapBlock: {
      backgroundColor: C.contentSurface,
      borderRadius: Radius.xl,
      padding: Space.md,
      gap: Space.xs,
    },
    gapText: { ...Type.secondary, color: C.textTertiary, flex: 1 },
    source: { ...Type.caption, color: C.textTertiary },
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
    actionPrimary: { backgroundColor: C.primary, flexGrow: 1 },
    actionActive: { backgroundColor: C.primaryLight },
    actionText: { ...Type.compact, color: C.textSecondary, fontWeight: "600" },
    actionTextPrimary: { color: C.onPrimary },
    actionTextActive: { color: C.primary },
    pressed: { opacity: 0.68 },
  });
}
