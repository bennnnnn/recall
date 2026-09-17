import { useCallback, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Alert, Text, View } from "react-native";
import { Redirect, useLocalSearchParams, useNavigation, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { AddAutomationSheet } from "@/components/automations/AddAutomationSheet";
import { AutomationActionsSheet } from "@/components/automations/AutomationActionsSheet";
import { automationFrequencyMessageKey } from "@/components/automations/AutomationFrequencyPicker";
import { makeAutomationsStyles } from "@/components/automations/automationsStyles";
import { IconButton } from "@/components/IconButton";
import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useAuth } from "@/contexts/AuthContext";
import { useAutomationDetail } from "@/hooks/useAutomationDetail";
import { describeLastRun, formatScheduleAt, shareAutomation } from "@/lib/automations/schedule";
import { IconSize } from "@/lib/icons";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { useTheme } from "@/lib/theme";

export default function AutomationDetailScreen() {
  const owner = useAccountViewOwner();
  return <AutomationDetailContent key={owner.key} isCurrent={owner.isCurrent} />;
}

function AutomationDetailContent({ isCurrent }: { isCurrent: () => boolean }) {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { token } = useAuth();
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const C = useTheme();
  const s = useMemo(() => makeAutomationsStyles(C), [C]);
  const navigation = useNavigation();
  const router = useRouter();
  const { automation, loading, error, saving, deleted, refresh, update, togglePause, remove } =
    useAutomationDetail(id ?? "", isCurrent);
  const [menuOpen, setMenuOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const sharing = useRef(false);

  const openMenu = useCallback(() => {
    if (isCurrent()) setMenuOpen(true);
  }, [isCurrent]);

  useLayoutEffect(() => {
    navigation.setOptions({
      title: automation ? automation.prompt : t("automations.title"),
      headerRight: automation
        ? () => (
            <IconButton
              name="ellipsis-horizontal"
              size={IconSize.md}
              accessibilityLabel={t("automations.menu_a11y")}
              onPress={openMenu}
            />
          )
        : undefined,
    });
  }, [navigation, automation, t, openMenu]);

  const confirmDelete = useCallback(() => {
    setMenuOpen(false);
    Alert.alert(
      t("automations.delete_confirm_title"),
      t("automations.delete_confirm_body"),
      [
        { text: t("common.cancel"), style: "cancel" },
        {
          text: t("common.delete"),
          style: "destructive",
          onPress: () =>
            void remove(() => {
              if (isCurrent() && router.canGoBack()) router.back();
            }),
        },
      ],
    );
  }, [t, remove, isCurrent, router]);

  if (!token) return <Redirect href="/login" />;
  if (deleted) return <Redirect href="/automations" />;

  if (loading && !automation) return <SkeletonList />;

  if (error || !automation) {
    return (
      <StateView
        variant="error"
        title={t("common.error")}
        onRetry={() => {
          if (isCurrent()) void refresh();
        }}
        retryLabel={t("common.retry")}
      />
    );
  }

  return (
    <View style={s.root}>
      <View style={s.detailHeader}>
        <Text style={s.detailPrompt}>{automation.prompt}</Text>
        {automation.status === "paused" ? (
          <View style={[s.cardStatusPill, s.cardStatusPillPaused, s.detailStatusPill]}>
            <Text style={[s.cardStatusPillText, s.cardStatusPillTextPaused]}>
              {t("automations.status_paused")}
            </Text>
          </View>
        ) : null}
      </View>

      <View style={s.detailInfoCard}>
        <View style={s.detailInfoRow}>
          <Text style={s.detailInfoLabel}>{t("automations.frequency_label")}</Text>
          <Text style={s.detailInfoValue}>
            {automation.status === "completed"
              ? t("automations.status_completed")
              : t(automationFrequencyMessageKey(automation.frequency))}
          </Text>
        </View>
        {automation.status !== "completed" ? (
          <View style={[s.detailInfoRow, s.detailInfoRowBorder]}>
            <Text style={s.detailInfoLabel}>{t("automations.field_time")}</Text>
            <Text style={s.detailInfoValue}>{formatScheduleAt(automation.next_run_at)}</Text>
          </View>
        ) : null}
        <View style={[s.detailInfoRow, s.detailInfoRowBorder]}>
          <Text style={s.detailInfoLabel}>{t("automations.field_last_run")}</Text>
          <Text style={s.detailInfoValue}>{describeLastRun(automation, t)}</Text>
        </View>
      </View>

      <AutomationActionsSheet
        visible={menuOpen}
        status={automation.status}
        onClose={() => {
          if (isCurrent()) setMenuOpen(false);
        }}
        onEdit={() => {
          setMenuOpen(false);
          setEditOpen(true);
        }}
        onShare={() => {
          // Keep the sheet mounted until Share.share resolves — closing it
          // first can make iOS drop the OS activity controller.
          if (sharing.current || !automation) return;
          sharing.current = true;
          void shareAutomation(automation, t)
            .catch(() => {
              if (isCurrent()) reportRecoverableError(feedback, t("automations.share_failed"));
            })
            .finally(() => {
              sharing.current = false;
              if (isCurrent()) setMenuOpen(false);
            });
        }}
        onTogglePause={() => {
          setMenuOpen(false);
          togglePause();
        }}
        onDelete={confirmDelete}
      />

      <AddAutomationSheet
        visible={editOpen}
        saving={saving}
        initial={{
          prompt: automation.prompt,
          frequency: automation.frequency,
          nextRunAt: new Date(automation.next_run_at),
        }}
        onClose={() => {
          if (isCurrent()) setEditOpen(false);
        }}
        onSave={(prompt, frequency, nextRunAt) => {
          void update({ prompt, frequency, next_run_at: nextRunAt.toISOString() });
          setEditOpen(false);
        }}
      />
    </View>
  );
}
