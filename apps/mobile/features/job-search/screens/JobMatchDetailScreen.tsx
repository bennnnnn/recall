import { useMemo } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Icon } from "@/ui/icons/Icon";
import { HeaderButton, HEADER_BUTTON_SIZE } from "@/ui/controls/HeaderButton";
import { CoverLetterSheet } from "@/features/job-search/components/CoverLetterSheet";
import { CompanyLogo } from "@/features/job-search/components/CompanyLogo";
import { JobFitBadge } from "@/features/job-search/components/JobFitBadge";
import { JobMatchDetailSkeleton } from "@/features/job-search/components/JobMatchDetailSkeleton";
import { JobMatchMetaChips } from "@/features/job-search/components/JobMatchMetaChips";
import { JobMatchReasons } from "@/features/job-search/components/JobMatchReasons";
import { StateView } from "@/ui/feedback/StateView";
import { useAuth } from "@/contexts/AuthContext";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { useJobMatchDetail } from "@/features/job-search/hooks/useJobMatchDetail";
import { selection, tap } from "@/lib/haptics";
import { canToggleApplied, hasApplied } from "@/features/job-search/model/stages";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { IconSize } from "@/ui/icons/sizes";

export default function JobMatchDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const owner = useAccountViewOwner();
  return (
    <JobMatchDetailView
      key={`${owner.key}:${id ?? ""}`}
      id={id}
      isCurrent={owner.isCurrent}
    />
  );
}

function JobMatchDetailView({
  id,
  isCurrent,
}: {
  id: string | undefined;
  isCurrent: () => boolean;
}) {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const { t } = useTranslation();
  const { user } = useAuth();
  const {
    match,
    loading,
    loadError,
    load,
    updateStatus,
    openJob,
    letterOpen,
    setLetterOpen,
    letterLoading,
    letter,
    generateLetter,
  } = useJobMatchDetail(id, isCurrent);
  const isPro = user?.plan === "pro" && !match?.pro_required;
  const applicationStarted = match ? hasApplied(match.status) : false;

  return (
    <View style={[s.screen, { paddingTop: insets.top }]}>
      <View style={s.header}>
        <HeaderButton
          icon="arrow-left"
          variant="plain"
          onPress={() => router.back()}
          accessibilityLabel={t("common.back")}
        />
        <Text style={s.headerTitle} numberOfLines={1}>
          {match?.company ?? t("my_job.title")}
        </Text>
        <View style={s.headerButton} />
      </View>

      <KeyboardAvoidingView
        style={s.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        testID="job-match-detail-keyboard-view"
      >
      {loading ? (
        <JobMatchDetailSkeleton />
      ) : loadError && match == null ? (
        <StateView
          variant="error"
          title={t("my_job.refresh_error")}
          onRetry={() => void load()}
        />
      ) : match == null ? (
        <StateView
          variant="empty"
          icon="briefcase"
          title={t("my_job.detail_not_found")}
        />
      ) : (
        <ScrollView
          contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
          testID="job-match-detail-scroll"
        >
          <View style={s.headingRow}>
            <CompanyLogo company={match.company} uri={match.company_logo_url} size={56} />
            <View style={s.headingCopy}>
              <Text style={s.title}>{match.title}</Text>
              <Text style={s.company}>{match.company}</Text>
            </View>
            <JobFitBadge label={match.fit_label} outdated={match.outdated} />
          </View>

          {!isPro ? <Text style={s.company}>{t("my_job.expired_pro_body")}</Text> : null}
          <JobMatchMetaChips match={match} maxSkills={8} />

          {match.summary ? <Text style={s.summary}>{match.summary}</Text> : null}

          <JobMatchReasons match={match} />

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
              <Icon name="external-link" size={IconSize.sm} color={C.primary} />
              <Text style={[s.actionText, s.actionTextPrimary]}>{t("my_job.view_job")}</Text>
            </Pressable>
            <Pressable
              style={({ pressed }) => [
                s.action,
                applicationStarted && s.actionActive,
                pressed && s.pressed,
              ]}
              onPress={() => {
                selection();
                void updateStatus(match.status === "applied" ? "new" : "applied");
              }}
              accessibilityRole="button"
              disabled={!isPro || !canToggleApplied(match.status)}
              accessibilityState={{
                selected: applicationStarted,
                disabled: !isPro || !canToggleApplied(match.status),
              }}
            >
              <Icon
                name="check-circle"
                size={IconSize.sm}
                color={applicationStarted ? C.primary : C.textSecondary}
              />
              <Text
                style={[s.actionText, applicationStarted && s.actionTextActive]}
              >
                {applicationStarted ? t("my_job.applied") : t("my_job.i_applied")}
              </Text>
            </Pressable>
          </View>

          {isPro ? (
            <Pressable
              style={({ pressed }) => [s.letterCta, pressed && s.pressed]}
              onPress={() => void generateLetter()}
              accessibilityRole="button"
            >
              <Icon name="sparkles" size={IconSize.sm} color={C.primary} />
              <Text style={s.letterCtaText}>{t("my_job.cover_letter_cta")}</Text>
              <Icon name="chevron-right" size={IconSize.xs} color={C.textTertiary} />
            </Pressable>
          ) : null}

        </ScrollView>
      )}
      </KeyboardAvoidingView>

      <CoverLetterSheet
        visible={letterOpen}
        loading={letterLoading}
        letter={letter}
        onClose={() => setLetterOpen(false)}
      />
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    screen: { flex: 1, backgroundColor: C.bg },
    flex: { flex: 1 },
    header: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      paddingHorizontal: Space.sm,
      paddingVertical: Space.xs,
    },
    headerButton: { width: HEADER_BUTTON_SIZE, height: HEADER_BUTTON_SIZE },
    headerTitle: {
      ...Type.navTitle,
      color: C.text,
      flex: 1,
      textAlign: "center",
    },
    content: { padding: Space.md, gap: Space.md },
    headingRow: { flexDirection: "row", alignItems: "center", gap: Space.sm },
    headingCopy: { flex: 1, minWidth: 0 },
    title: { ...Type.navTitle, color: C.text, ...Weight.bold },
    company: { ...Type.body, color: C.textSecondary, marginTop: 2 },
    summary: { ...Type.secondary, color: C.text },
    source: { ...Type.caption, color: C.textTertiary },
    actions: {
      flexDirection: "row",
      gap: Space.sm,
      paddingHorizontal: Space.xs,
    },
    action: {
      flex: 1,
      minHeight: Space.lg * 2,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: Space.xs,
      paddingHorizontal: Space.sm,
      paddingVertical: Space.xs,
      borderRadius: Radius.full,
      backgroundColor: C.surfaceAlt,
    },
    actionPrimary: {
      backgroundColor: C.primaryLight,
    },
    actionActive: { backgroundColor: C.primaryLight },
    actionText: { ...Type.compact, color: C.textSecondary, ...Weight.semibold, flexShrink: 1, textAlign: "center" },
    actionTextPrimary: { color: C.primary },
    actionTextActive: { color: C.primary },
    letterCta: {
      minHeight: 52,
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      backgroundColor: C.primaryLight,
      borderRadius: Radius.xl,
      paddingHorizontal: Space.md,
    },
    letterCtaText: {
      ...Type.secondary,
      color: C.primary,
      ...Weight.bold,
      flex: 1,
    },
    pressed: { opacity: 0.68 },
  });
}
