import { useCallback, useMemo, useState } from "react";
import {
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Redirect, useFocusEffect } from "expo-router";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { JobMatchCard } from "@/components/jobSearch/JobMatchCard";
import { JobSearchSetupSheet } from "@/components/jobSearch/JobSearchSetupSheet";
import { SkeletonList } from "@/components/SkeletonLoader";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { useAuth } from "@/contexts/AuthContext";
import { useJobSearch } from "@/hooks/useJobSearch";
import type { JobMatch, JobMatchStatus, JobSearchProfile } from "@/lib/api";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { notifyWarning, selection, tap } from "@/lib/haptics";
import { type Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Tab = "matches" | "saved" | "applied";

function cadence(profile: JobSearchProfile, t: TFunction): string {
  return t(`my_job.cadence_${profile.frequency}`, { count: profile.result_count });
}

function nextDelivery(profile: JobSearchProfile): string {
  const date = new Date(profile.next_run_at);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function TabButton({
  label,
  count,
  active,
  onPress,
}: {
  label: string;
  count: number;
  active: boolean;
  onPress: () => void;
}) {
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  return (
    <Pressable
      style={({ pressed }) => [s.tab, active && s.tabActive, pressed && s.pressed]}
      onPress={() => {
        selection();
        onPress();
      }}
      accessibilityRole="tab"
      accessibilityState={{ selected: active }}
    >
      <Text style={[s.tabText, active && s.tabTextActive]}>{label}</Text>
      {count > 0 ? (
        <View style={[s.tabCount, active && s.tabCountActive]}>
          <Text style={[s.tabCountText, active && s.tabCountTextActive]}>{count}</Text>
        </View>
      ) : null}
    </Pressable>
  );
}

export default function MyJobScreen() {
  const owner = useAccountViewOwner();
  return <MyJobContent key={owner.key} isCurrent={owner.isCurrent} />;
}

function MyJobContent({ isCurrent }: { isCurrent: () => boolean }) {
  const { token, user } = useAuth();
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const {
    dashboard,
    loading,
    busy,
    error,
    refresh,
    save,
    setSearchStatus,
    setMatchStatus,
    runNow,
    remove,
  } = useJobSearch(isCurrent);
  const [setupOpen, setSetupOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("matches");
  const [refreshing, setRefreshing] = useState(false);

  useFocusEffect(
    useCallback(() => {
      void refresh({ silent: true });
    }, [refresh]),
  );

  const profile = dashboard.profile;
  const counts = useMemo(
    () => ({
      matches: dashboard.matches.filter((item) => item.status === "new").length,
      saved: dashboard.matches.filter((item) => item.status === "saved").length,
      applied: dashboard.matches.filter((item) => item.status === "applied").length,
    }),
    [dashboard.matches],
  );
  const visibleMatches = useMemo(() => {
    const status: JobMatchStatus = tab === "matches" ? "new" : tab;
    return dashboard.matches.filter((item) => item.status === status);
  }, [dashboard.matches, tab]);

  const confirmDelete = () => {
    Alert.alert(t("my_job.delete_title"), t("my_job.delete_body"), [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("common.delete"),
        style: "destructive",
        onPress: () => {
          notifyWarning();
          void remove();
        },
      },
    ]);
  };

  if (!token) return <Redirect href="/login" />;
  if (loading && !profile) return <SkeletonList />;

  if (!profile) {
    return (
      <View style={s.root}>
        <View style={s.onboarding}>
          <View style={s.heroIcon}>
            <Icon name="briefcase-outline" size={34} color={C.primary} />
          </View>
          <Text style={s.heroTitle}>{t("my_job.hero_title")}</Text>
          <Text style={s.heroBody}>{t("my_job.hero_body")}</Text>

          <View style={s.benefits}>
            {([
              ["search-outline", t("my_job.benefit_fresh_title"), t("my_job.benefit_fresh_body")],
              ["sparkles-outline", t("my_job.benefit_matched_title"), t("my_job.benefit_matched_body")],
              ["notifications-outline", t("my_job.benefit_delivered_title"), t("my_job.benefit_delivered_body")],
            ] as const).map(([icon, title, body]) => (
              <View key={title} style={s.benefitRow}>
                <View style={s.benefitIcon}>
                  <Icon name={icon as "search-outline"} size={21} color={C.primary} />
                </View>
                <View style={s.benefitCopy}>
                  <Text style={s.benefitTitle}>{title}</Text>
                  <Text style={s.benefitBody}>{body}</Text>
                </View>
              </View>
            ))}
          </View>

          <Pressable
            style={({ pressed }) => [s.primaryButton, pressed && s.pressed]}
            onPress={() => setSetupOpen(true)}
          >
            <Text style={s.primaryButtonText}>{t("my_job.setup_cta")}</Text>
            <Icon name="arrow-forward" size={20} color={C.onPrimary} />
          </Pressable>
          <Text style={s.planNote}>
            {user?.plan === "pro" ? t("my_job.plan_note_pro") : t("my_job.plan_note_free")}
          </Text>
        </View>

        <JobSearchSetupSheet
          visible={setupOpen}
          initial={null}
          busy={busy}
          onClose={() => setSetupOpen(false)}
          onSave={save}
        />
      </View>
    );
  }

  const emptyTitle =
    tab === "matches"
      ? t("my_job.empty_matches")
      : tab === "saved"
        ? t("my_job.empty_saved")
        : t("my_job.empty_applied");
  const emptyBody =
    tab === "matches"
      ? profile.last_run_at
        ? t("my_job.empty_matches_body_ran")
        : t("my_job.empty_matches_body_scheduled", { date: nextDelivery(profile) })
      : tab === "saved"
        ? t("my_job.empty_saved_body")
        : t("my_job.empty_applied_body");

  return (
    <View style={s.root}>
      <FlatList<JobMatch>
        data={visibleMatches}
        keyExtractor={(item) => item.id}
        contentContainerStyle={s.listContent}
        ItemSeparatorComponent={() => <View style={s.cardGap} />}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            tintColor={C.primary}
            onRefresh={async () => {
              setRefreshing(true);
              await refresh({ silent: true });
              if (isCurrent()) setRefreshing(false);
            }}
          />
        }
        ListHeaderComponent={
          <View style={s.headerStack}>
            <View style={s.searchCard}>
              <View style={s.searchTopRow}>
                <View style={s.searchCopy}>
                  <Text style={s.overline}>
                    {profile.status === "paused" ? t("my_job.status_paused") : t("my_job.status_your_search")}
                  </Text>
                  <Text style={s.searchTitle} numberOfLines={2}>
                    {profile.target_roles.join(" · ")}
                  </Text>
                </View>
                <Pressable
                  style={({ pressed }) => [s.iconButton, pressed && s.pressed]}
                  onPress={() => setSetupOpen(true)}
                  accessibilityRole="button"
                  accessibilityLabel={t("my_job.edit_a11y")}
                >
                  <Icon name="options-outline" size={21} color={C.text} />
                </Pressable>
              </View>

              <Text style={s.searchMeta}>
                {[profile.location, profile.work_modes.join(" / "), profile.experience_levels.join(" / ")]
                  .filter(Boolean)
                  .join(" · ")}
              </Text>
              <View style={s.searchDivider} />
              <View style={s.deliveryRow}>
                <View style={s.deliveryIcon}>
                  <Icon name="notifications-outline" size={19} color={C.primary} />
                </View>
                <View style={s.deliveryCopy}>
                  <Text style={s.deliveryTitle}>{cadence(profile, t)}</Text>
                  <Text style={s.deliveryMeta}>
                    {t("my_job.next_delivery", { date: nextDelivery(profile) })}
                  </Text>
                </View>
              </View>

              <View style={s.searchActions}>
                <Pressable
                  style={({ pressed }) => [s.secondaryButton, pressed && s.pressed]}
                  onPress={() => {
                    selection();
                    void setSearchStatus(profile.status === "paused" ? "active" : "paused");
                  }}
                  disabled={busy}
                >
                  <Icon
                    name={profile.status === "paused" ? "play-outline" : "pause-outline"}
                    size={18}
                    color={C.text}
                  />
                  <Text style={s.secondaryButtonText}>
                    {profile.status === "paused" ? t("my_job.resume") : t("my_job.pause")}
                  </Text>
                </Pressable>
                {user?.plan === "pro" ? (
                  <Pressable
                    style={({ pressed }) => [s.secondaryButton, pressed && s.pressed]}
                    onPress={() => {
                      tap();
                      void runNow();
                    }}
                    disabled={busy}
                  >
                    <Icon name="refresh" size={18} color={C.text} />
                    <Text style={s.secondaryButtonText}>{t("my_job.find_now")}</Text>
                  </Pressable>
                ) : null}
                <Pressable
                  style={({ pressed }) => [s.moreButton, pressed && s.pressed]}
                  onPress={confirmDelete}
                  disabled={busy}
                  accessibilityRole="button"
                  accessibilityLabel={t("my_job.delete_a11y")}
                >
                  <Icon name="trash-outline" size={19} color={C.danger} />
                </Pressable>
              </View>
            </View>

            <View style={s.tabs} accessibilityRole="tablist">
              <TabButton label={t("my_job.tab_matches")} count={counts.matches} active={tab === "matches"} onPress={() => setTab("matches")} />
              <TabButton label={t("my_job.tab_saved")} count={counts.saved} active={tab === "saved"} onPress={() => setTab("saved")} />
              <TabButton label={t("my_job.tab_applied")} count={counts.applied} active={tab === "applied"} onPress={() => setTab("applied")} />
            </View>

            {error ? (
              <Pressable style={s.errorCard} onPress={() => void refresh()}>
                <Icon name="alert-circle-outline" size={20} color={C.danger} />
                <Text style={s.errorText}>{t("my_job.refresh_error")}</Text>
              </Pressable>
            ) : null}

            {visibleMatches.length === 0 ? (
              <View style={s.emptyCard}>
                <View style={s.emptyIcon}>
                  <Icon
                    name={tab === "matches" ? "search-outline" : tab === "saved" ? "bookmark-outline" : "checkmark-circle-outline"}
                    size={28}
                    color={C.primary}
                  />
                </View>
                <Text style={s.emptyTitle}>{emptyTitle}</Text>
                <Text style={s.emptyBody}>{emptyBody}</Text>
              </View>
            ) : null}
          </View>
        }
        renderItem={({ item }) => (
          <JobMatchCard match={item} onStatus={(status) => void setMatchStatus(item.id, status)} />
        )}
      />

      <JobSearchSetupSheet
        visible={setupOpen}
        initial={profile}
        busy={busy}
        onClose={() => setSetupOpen(false)}
        onSave={save}
      />
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: C.bg },
    onboarding: {
      flex: 1,
      paddingHorizontal: Space.lg,
      paddingTop: Space.xl,
      paddingBottom: Space.xl,
      alignItems: "center",
    },
    heroIcon: {
      width: 72,
      height: 72,
      borderRadius: 24,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: C.primaryLight,
      marginBottom: Space.lg,
    },
    heroTitle: { ...Type.display, color: C.text, textAlign: "center" },
    heroBody: {
      ...Type.body,
      color: C.textSecondary,
      textAlign: "center",
      maxWidth: 520,
      marginTop: Space.sm,
    },
    benefits: { width: "100%", maxWidth: 560, gap: Space.md, marginTop: Space.xl },
    benefitRow: { flexDirection: "row", alignItems: "flex-start", gap: Space.sm },
    benefitIcon: {
      width: 42,
      height: 42,
      borderRadius: 14,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: C.surface,
    },
    benefitCopy: { flex: 1 },
    benefitTitle: { ...Type.label, color: C.text },
    benefitBody: { ...Type.secondary, color: C.textSecondary, marginTop: 2 },
    primaryButton: {
      width: "100%",
      maxWidth: 560,
      minHeight: 56,
      borderRadius: Radius.full,
      backgroundColor: C.primary,
      paddingHorizontal: Space.lg,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: Space.xs,
      marginTop: Space.xl,
    },
    primaryButtonText: { ...Type.body, color: C.onPrimary, fontWeight: "700" },
    planNote: { ...Type.caption, color: C.textTertiary, marginTop: Space.sm },
    listContent: { padding: Space.md, paddingBottom: Space.xl },
    headerStack: { gap: Space.md, marginBottom: Space.md },
    searchCard: { backgroundColor: C.surface, borderRadius: 26, padding: Space.lg, gap: Space.sm },
    searchTopRow: { flexDirection: "row", alignItems: "flex-start", gap: Space.sm },
    searchCopy: { flex: 1 },
    overline: { ...Type.overline, color: C.primary },
    searchTitle: { ...Type.title, color: C.text, fontWeight: "700", marginTop: Space.xs },
    searchMeta: { ...Type.secondary, color: C.textSecondary },
    iconButton: {
      width: 42,
      height: 42,
      borderRadius: 21,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: C.surfaceAlt,
    },
    searchDivider: { height: StyleSheet.hairlineWidth, backgroundColor: C.border, marginVertical: Space.xs },
    deliveryRow: { flexDirection: "row", alignItems: "center", gap: Space.sm },
    deliveryIcon: {
      width: 38,
      height: 38,
      borderRadius: 19,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: C.primaryLight,
    },
    deliveryCopy: { flex: 1 },
    deliveryTitle: { ...Type.label, color: C.text },
    deliveryMeta: { ...Type.caption, color: C.textTertiary, marginTop: 2 },
    searchActions: { flexDirection: "row", flexWrap: "wrap", gap: Space.xs, marginTop: Space.sm },
    secondaryButton: {
      minHeight: 42,
      paddingHorizontal: Space.md,
      borderRadius: Radius.full,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: Space.xxs,
      backgroundColor: C.surfaceAlt,
    },
    secondaryButtonText: { ...Type.compact, color: C.text, fontWeight: "600" },
    moreButton: {
      width: 42,
      height: 42,
      borderRadius: 21,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: C.dangerLight,
    },
    tabs: {
      flexDirection: "row",
      padding: 4,
      borderRadius: Radius.full,
      backgroundColor: C.surface,
    },
    tab: {
      flex: 1,
      minHeight: 44,
      borderRadius: Radius.full,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: Space.xxs,
    },
    tabActive: { backgroundColor: C.bg },
    tabText: { ...Type.compact, color: C.textSecondary, fontWeight: "600" },
    tabTextActive: { color: C.text },
    tabCount: {
      minWidth: 22,
      height: 22,
      borderRadius: 11,
      paddingHorizontal: 6,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: C.surfaceAlt,
    },
    tabCountActive: { backgroundColor: C.primaryLight },
    tabCountText: { ...Type.caption, color: C.textSecondary },
    tabCountTextActive: { color: C.primary },
    cardGap: { height: Space.md },
    emptyCard: { alignItems: "center", paddingVertical: 48, paddingHorizontal: Space.lg },
    emptyIcon: {
      width: 58,
      height: 58,
      borderRadius: 20,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: C.primaryLight,
    },
    emptyTitle: { ...Type.title, color: C.text, marginTop: Space.md, textAlign: "center" },
    emptyBody: { ...Type.secondary, color: C.textSecondary, marginTop: Space.xs, textAlign: "center", maxWidth: 420 },
    errorCard: {
      minHeight: 52,
      paddingHorizontal: Space.md,
      borderRadius: Radius.xl,
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      backgroundColor: C.dangerLight,
    },
    errorText: { ...Type.secondary, color: C.danger, flex: 1 },
    pressed: { opacity: 0.68 },
  });
}
