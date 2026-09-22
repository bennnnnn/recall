import { useCallback, useMemo, useState } from "react";
import { FlashList } from "@shopify/flash-list";
import {
  Alert,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Redirect, useFocusEffect, useRouter } from "expo-router";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { JobMatchCard } from "@/components/jobSearch/JobMatchCard";
import { JobSearchActionsSheet } from "@/components/jobSearch/JobSearchActionsSheet";
import {
  JobStageFilter,
  type JobStageFilterValue,
} from "@/components/jobSearch/JobStageFilter";
import { SearchProfileFields } from "@/components/jobSearch/SearchProfileFields";
import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { useAuth } from "@/contexts/AuthContext";
import { useJobSearch } from "@/hooks/useJobSearch";
import type { JobMatch, JobSearchProfile } from "@/lib/api";
import { filterAndSortMatches } from "@/lib/jobSearch/matchList";
import { nextDeliveryDate } from "@/lib/jobSearch/searchFields";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { notifyWarning, selection, tap } from "@/lib/haptics";
import { presentShareSheet } from "@/lib/share";
import { type Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Tab = "matches" | "saved" | "all";

function cadence(profile: JobSearchProfile, t: TFunction): string {
  return t(`my_job.cadence_${profile.frequency}`, {
    count: profile.result_count,
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
      style={({ pressed }) => [
        s.tab,
        active && s.tabActive,
        pressed && s.pressed,
      ]}
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
          <Text style={[s.tabCountText, active && s.tabCountTextActive]}>
            {count}
          </Text>
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
    setSearchStatus,
    setMatchStatus,
    setMatchSaved,
    runNow,
    remove,
  } = useJobSearch(isCurrent);
  const router = useRouter();
  const openSetup = useCallback(() => {
    tap();
    router.push("/my-job/setup");
  }, [router]);
  const [tab, setTab] = useState<Tab>("matches");
  const [stageFilter, setStageFilter] = useState<JobStageFilterValue>("all");
  const [refreshing, setRefreshing] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useFocusEffect(
    useCallback(() => {
      void refresh({ silent: true });
    }, [refresh]),
  );

  const profile = dashboard.profile;
  const counts = useMemo(
    () => ({
      all: dashboard.matches.filter((item) => item.status !== "hidden").length,
      matches: dashboard.matches.filter(
        (item) => item.status === "new" && !item.is_saved,
      ).length,
      saved: dashboard.matches.filter(
        (item) => item.is_saved && item.status !== "hidden",
      ).length,
      applied: dashboard.matches.filter((item) => item.status === "applied")
        .length,
      interviewing: dashboard.matches.filter(
        (item) => item.status === "interviewing",
      ).length,
      offer: dashboard.matches.filter((item) => item.status === "offer").length,
      rejected: dashboard.matches.filter((item) => item.status === "rejected")
        .length,
    }),
    [dashboard.matches],
  );
  const visibleMatches = useMemo(
    () =>
      filterAndSortMatches(
        dashboard.matches,
        tab === "matches" ? "new" : tab === "saved" ? "saved" : stageFilter,
        "best",
      ),
    [dashboard.matches, stageFilter, tab],
  );

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

  const handleEdit = () => {
    setMenuOpen(false);
    openSetup();
  };
  const handleTogglePause = () => {
    if (!profile) return;
    selection();
    setMenuOpen(false);
    void setSearchStatus(profile.status === "paused" ? "active" : "paused");
  };
  const handleShare = async () => {
    if (!profile) return;
    const message = [
      profile.target_roles.join(" · "),
      [profile.location, profile.work_modes.join(" / ")]
        .filter(Boolean)
        .join(" · "),
      cadence(profile, t),
    ]
      .filter(Boolean)
      .join("\n");
    // Keep the AppSheet up until the share sheet returns — closing the Modal
    // first tears down the presenter and iOS dismisses the activity sheet.
    try {
      await presentShareSheet({ message, title: t("my_job.title") });
    } catch {
      Alert.alert(t("my_job.share_failed"));
    } finally {
      setMenuOpen(false);
    }
  };
  const handleDelete = () => {
    setMenuOpen(false);
    confirmDelete();
  };

  if (!token) return <Redirect href="/login" />;
  if (loading && !profile) return <SkeletonList />;

  if (error && !profile) {
    return (
      <StateView
        variant="error"
        title={t("my_job.refresh_error")}
        onRetry={() => void refresh()}
      />
    );
  }

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
            {(
              [
                [
                  "search-outline",
                  t("my_job.benefit_fresh_title"),
                  t("my_job.benefit_fresh_body"),
                ],
                [
                  "sparkles-outline",
                  t("my_job.benefit_matched_title"),
                  t("my_job.benefit_matched_body"),
                ],
                [
                  "notifications-outline",
                  t("my_job.benefit_delivered_title"),
                  t("my_job.benefit_delivered_body"),
                ],
              ] as const
            ).map(([icon, title, body]) => (
              <View key={title} style={s.benefitRow}>
                <View style={s.benefitIcon}>
                  <Icon
                    name={icon as "search-outline"}
                    size={21}
                    color={C.primary}
                  />
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
            onPress={openSetup}
            accessibilityRole="button"
            accessibilityLabel={t("my_job.setup_cta")}
          >
            <Text style={s.primaryButtonText}>{t("my_job.setup_cta")}</Text>
            <Icon name="arrow-forward" size={20} color={C.onPrimary} />
          </Pressable>
          <Text style={s.planNote}>
            {user?.plan === "pro"
              ? t("my_job.plan_note_pro")
              : t("my_job.plan_note_free")}
          </Text>
        </View>
      </View>
    );
  }

  const effectiveFilter = tab === "all" ? stageFilter : tab;
  const emptyTitle =
    effectiveFilter === "saved"
      ? t("my_job.empty_saved")
      : effectiveFilter === "applied"
        ? t("my_job.empty_applied")
        : effectiveFilter === "interviewing"
          ? t("my_job.empty_interviewing")
          : effectiveFilter === "offer"
            ? t("my_job.empty_offers")
            : effectiveFilter === "rejected"
              ? t("my_job.empty_rejected")
              : t("my_job.empty_matches");
  const emptyBody =
    effectiveFilter === "saved"
      ? t("my_job.empty_saved_body")
      : effectiveFilter === "applied"
        ? t("my_job.empty_applied_body")
        : effectiveFilter === "interviewing" ||
            effectiveFilter === "offer" ||
            effectiveFilter === "rejected"
          ? t("my_job.empty_stage_body")
          : profile.last_run_at
            ? t("my_job.empty_matches_body_ran")
            : t("my_job.empty_matches_body_scheduled", {
                date: nextDeliveryDate(profile),
              });
  const emptyIcon =
    effectiveFilter === "saved"
      ? "bookmark-outline"
      : effectiveFilter === "applied"
        ? "checkmark-circle-outline"
        : effectiveFilter === "interviewing"
          ? "people-outline"
          : effectiveFilter === "offer"
            ? "trophy-outline"
            : effectiveFilter === "rejected"
              ? "remove-circle-outline"
              : "search-outline";

  return (
    <View style={s.root}>
      <FlashList<JobMatch>
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
                    {profile.status === "paused"
                      ? t("my_job.status_paused")
                      : t("my_job.status_your_search")}
                  </Text>
                  <Text style={s.searchTitle} numberOfLines={2}>
                    {profile.target_roles.join(" · ")}
                  </Text>
                </View>
                <Pressable
                  style={({ pressed }) => [s.iconButton, pressed && s.pressed]}
                  onPress={() => {
                    tap();
                    setMenuOpen(true);
                  }}
                  accessibilityRole="button"
                  accessibilityLabel={t("my_job.menu_a11y")}
                >
                  <Icon name="ellipsis-horizontal" size={21} color={C.text} />
                </Pressable>
              </View>

              <SearchProfileFields profile={profile} />
            </View>

            <View style={s.tabs} accessibilityRole="tablist">
              <TabButton
                label={t("my_job.tab_matches")}
                count={counts.matches}
                active={tab === "matches"}
                onPress={() => setTab("matches")}
              />
              <TabButton
                label={t("my_job.tab_saved")}
                count={counts.saved}
                active={tab === "saved"}
                onPress={() => setTab("saved")}
              />
              <JobStageFilter
                value={stageFilter}
                counts={{
                  all: counts.all,
                  applied: counts.applied,
                  interviewing: counts.interviewing,
                  offer: counts.offer,
                  rejected: counts.rejected,
                }}
                active={tab === "all"}
                onOpen={() => setTab("all")}
                onChange={setStageFilter}
              />
            </View>

            {error ? (
              <Pressable style={s.errorCard} onPress={() => void refresh()}>
                <Icon name="alert-circle-outline" size={20} color={C.danger} />
                <Text style={s.errorText}>{t("my_job.refresh_error")}</Text>
              </Pressable>
            ) : null}

            {profile.last_run_status === "error" ? (
              <View style={s.runErrorCard} accessibilityRole="alert">
                <Icon name="alert-circle-outline" size={21} color={C.danger} />
                <View style={s.runErrorCopy}>
                  <Text style={s.runErrorTitle}>
                    {t("my_job.run_failed_title")}
                  </Text>
                  <Text style={s.runErrorBody}>
                    {t("my_job.run_failed_body")}
                  </Text>
                </View>
                <Pressable
                  style={({ pressed }) => [s.retryButton, pressed && s.pressed]}
                  onPress={() => void runNow()}
                  disabled={busy}
                  accessibilityRole="button"
                >
                  <Text style={s.retryButtonText}>{t("common.retry")}</Text>
                </Pressable>
              </View>
            ) : null}

            {visibleMatches.length === 0 ? (
              <StateView
                variant="empty"
                compact
                icon={emptyIcon}
                title={emptyTitle}
                message={emptyBody}
              />
            ) : null}
          </View>
        }
        renderItem={({ item }) => (
          <JobMatchCard
            match={item}
            onStatus={(status) => void setMatchStatus(item.id, status)}
            onSavedChange={(saved) => void setMatchSaved(item.id, saved)}
            onPress={() => router.push(`/my-job/match/${item.id}`)}
          />
        )}
      />
      <JobSearchActionsSheet
        visible={menuOpen}
        paused={profile.status === "paused"}
        busy={busy}
        onClose={() => setMenuOpen(false)}
        onEdit={handleEdit}
        onTogglePause={handleTogglePause}
        onShare={() => void handleShare()}
        onDelete={handleDelete}
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
    benefits: {
      width: "100%",
      maxWidth: 560,
      gap: Space.md,
      marginTop: Space.xl,
    },
    benefitRow: {
      flexDirection: "row",
      alignItems: "flex-start",
      gap: Space.sm,
    },
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
    searchCard: {
      backgroundColor: C.surface,
      borderRadius: 26,
      padding: Space.lg,
      gap: Space.sm,
    },
    searchTopRow: {
      flexDirection: "row",
      alignItems: "flex-start",
      gap: Space.sm,
    },
    searchCopy: { flex: 1 },
    overline: { ...Type.overline, color: C.primary },
    searchTitle: {
      ...Type.title,
      color: C.text,
      fontWeight: "700",
      marginTop: Space.xs,
    },
    iconButton: {
      width: Space.minTouch,
      height: Space.minTouch,
      borderRadius: Space.minTouch / 2,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: C.surfaceAlt,
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
    runErrorCard: {
      minHeight: 72,
      padding: Space.md,
      borderRadius: Radius.xl,
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      backgroundColor: C.dangerLight,
    },
    runErrorCopy: { flex: 1, minWidth: 0 },
    runErrorTitle: { ...Type.label, color: C.danger },
    runErrorBody: { ...Type.compact, color: C.textSecondary, marginTop: 2 },
    retryButton: {
      minHeight: 40,
      paddingHorizontal: Space.md,
      borderRadius: Radius.full,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: C.surface,
    },
    retryButtonText: { ...Type.compact, color: C.danger, fontWeight: "700" },
    pressed: { opacity: 0.68 },
  });
}
