import { useMemo } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Icon } from "@/ui/icons/Icon";
import { CoverLetterSheet } from "@/features/job-search/components/CoverLetterSheet";
import { CompanyLogo } from "@/features/job-search/components/CompanyLogo";
import { JobFitBadge } from "@/features/job-search/components/JobFitBadge";
import { JobMatchDetailSkeleton } from "@/features/job-search/components/JobMatchDetailSkeleton";
import { JobMatchMetaChips } from "@/features/job-search/components/JobMatchMetaChips";
import { JobMatchReasons } from "@/features/job-search/components/JobMatchReasons";
import { SettingsPickerSheet } from "@/components/settings/SettingsPickerSheet";
import { StateView } from "@/ui/feedback/StateView";
import { useAuth } from "@/contexts/AuthContext";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { useJobMatchDetail } from "@/features/job-search/hooks/useJobMatchDetail";
import { type JobMatchStatus } from "@/lib/api";
import { selection, tap } from "@/lib/haptics";
import { canToggleApplied, hasApplied } from "@/features/job-search/model/stages";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";

const STAGES: JobMatchStatus[] = [
  "new",
  "applied",
  "interviewing",
  "offer",
  "rejected",
];

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
  const isPro = user?.plan === "pro";
  const {
    match,
    loading,
    loadError,
    load,
    updateStatus,
    updateSaved,
    notesDraft,
    setNotesDraft,
    saveNotes,
    openJob,
    stageOpen,
    setStageOpen,
    letterOpen,
    setLetterOpen,
    letterLoading,
    letter,
    generateLetter,
  } = useJobMatchDetail(id, isCurrent);

  const stageLabel = (status: JobMatchStatus): string => {
    if (status === "applied") return t("my_job.applied");
    if (status === "hidden") return t("my_job.not_interested");
    return t(`my_job.stage_${status}`);
  };
  const applicationStarted = match ? hasApplied(match.status) : false;

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
          icon="briefcase-outline"
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
            <JobFitBadge score={match.match_score} />
          </View>

          <JobMatchMetaChips match={match} maxSkills={8} />

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
              <Icon name="open-outline" size={18} color={C.primary} />
              <Text style={[s.actionText, s.actionTextPrimary]}>{t("my_job.view_job")}</Text>
            </Pressable>
            <Pressable
              style={({ pressed }) => [
                s.action,
                match.is_saved && s.actionActive,
                pressed && s.pressed,
              ]}
              onPress={() => {
                selection();
                void updateSaved(!match.is_saved);
              }}
              accessibilityRole="button"
              accessibilityState={{ selected: match.is_saved }}
            >
              <Icon
                name={match.is_saved ? "bookmark" : "bookmark-outline"}
                size={18}
                color={match.is_saved ? C.primary : C.textSecondary}
              />
              <Text
                style={[s.actionText, match.is_saved && s.actionTextActive]}
              >
                {match.is_saved ? t("my_job.saved") : t("my_job.save")}
              </Text>
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
              disabled={!canToggleApplied(match.status)}
              accessibilityState={{
                selected: applicationStarted,
                disabled: !canToggleApplied(match.status),
              }}
            >
              <Icon
                name="checkmark-circle-outline"
                size={18}
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
              <Icon name="sparkles-outline" size={18} color={C.primary} />
              <Text style={s.letterCtaText}>{t("my_job.cover_letter_cta")}</Text>
              <Icon name="chevron-forward" size={16} color={C.textTertiary} />
            </Pressable>
          ) : null}

          <Pressable
            style={({ pressed }) => [s.stageRow, pressed && s.pressed]}
            onPress={() => {
              tap();
              setStageOpen(true);
            }}
            accessibilityRole="button"
            accessibilityLabel={t("my_job.stage_label")}
          >
            <Text style={s.sectionTitle}>{t("my_job.stage_label")}</Text>
            <View style={s.stageValue}>
              <Text style={s.stageValueText}>{stageLabel(match.status)}</Text>
              <Icon name="chevron-down" size={16} color={C.textTertiary} />
            </View>
          </Pressable>

          <View style={s.notesBlock}>
            <Text style={s.sectionTitle}>{t("my_job.notes_label")}</Text>
            <TextInput
              style={s.notesInput}
              value={notesDraft}
              onChangeText={setNotesDraft}
              onBlur={saveNotes}
              placeholder={t("my_job.notes_placeholder")}
              placeholderTextColor={C.textTertiary}
              multiline
            />
          </View>
        </ScrollView>
      )}
      </KeyboardAvoidingView>

      {match != null ? (
        <SettingsPickerSheet
          visible={stageOpen}
          title={t("my_job.stage_label")}
          options={STAGES.map((stage) => ({ key: stage, label: stageLabel(stage) }))}
          selectedKey={match.status}
          onClose={() => setStageOpen(false)}
          onSelect={(key) => {
            setStageOpen(false);
            selection();
            void updateStatus(key as JobMatchStatus);
          }}
        />
      ) : null}

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
    content: { padding: Space.md, gap: Space.md },
    headingRow: { flexDirection: "row", alignItems: "center", gap: Space.sm },
    headingCopy: { flex: 1, minWidth: 0 },
    title: { ...Type.navTitle, color: C.text, ...Weight.bold },
    company: { ...Type.body, color: C.textSecondary, marginTop: 2 },
    sectionTitle: { ...Type.label, color: C.text },
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
    actionPrimary: {
      backgroundColor: C.primaryLight,
      paddingHorizontal: Space.xs,
    },
    actionActive: { backgroundColor: C.primaryLight },
    actionText: { ...Type.compact, color: C.textSecondary, ...Weight.semibold },
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
    stageRow: {
      minHeight: 52,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      backgroundColor: C.surface,
      borderRadius: Radius.xl,
      paddingHorizontal: Space.md,
    },
    stageValue: { flexDirection: "row", alignItems: "center", gap: Space.xxs },
    stageValueText: { ...Type.secondary, color: C.primary, ...Weight.semibold },
    notesBlock: {
      backgroundColor: C.surface,
      borderRadius: Radius.xl,
      padding: Space.md,
      gap: Space.xs,
    },
    notesInput: {
      ...Type.secondary,
      color: C.text,
      minHeight: 88,
      textAlignVertical: "top",
      backgroundColor: C.surfaceAlt,
      borderRadius: Radius.md,
      padding: Space.sm,
    },
    pressed: { opacity: 0.68 },
  });
}
