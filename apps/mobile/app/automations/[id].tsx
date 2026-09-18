import { useCallback, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Alert, Pressable, Text, View } from "react-native";
import { Redirect, useLocalSearchParams, useNavigation, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { AddAutomationSheet } from "@/components/automations/AddAutomationSheet";
import { AutomationActionsSheet } from "@/components/automations/AutomationActionsSheet";
import { automationFrequencyMessageKey } from "@/components/automations/AutomationFrequencyPicker";
import { AutomationTranscript } from "@/components/automations/AutomationTranscript";
import { makeAutomationsStyles } from "@/components/automations/automationsStyles";
import { Icon } from "@/components/Icon";
import { IconButton } from "@/components/IconButton";
import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useAuth } from "@/contexts/AuthContext";
import { useAutomationDetail } from "@/hooks/useAutomationDetail";
import {
  automationDisplayTitle,
  formatAutomationScheduleDay,
  shareAutomation,
} from "@/lib/automations/schedule";
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
  const { automation, messages, loading, error, saving, deleted, refresh, update, togglePause, remove } =
    useAutomationDetail(id ?? "", isCurrent);
  const [menuOpen, setMenuOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const sharing = useRef(false);

  const openMenu = useCallback(() => {
    if (isCurrent()) setMenuOpen(true);
  }, [isCurrent]);

  const openEditor = useCallback(() => {
    if (isCurrent() && automation?.status !== "completed") setEditOpen(true);
  }, [isCurrent, automation?.status]);

  useLayoutEffect(() => {
    navigation.setOptions({
      title: "",
      headerRight: automation
        ? () => (
            <View style={s.detailHeaderActions}>
              {automation.status !== "completed" ? (
                <IconButton
                  name={automation.status === "paused" ? "play-outline" : "pause-outline"}
                  size={IconSize.md}
                  accessibilityLabel={t(
                    automation.status === "paused" ? "automations.resume" : "automations.pause",
                  )}
                  onPress={togglePause}
                />
              ) : null}
              <IconButton
                name="ellipsis-vertical"
                size={IconSize.md}
                accessibilityLabel={t("automations.menu_a11y")}
                onPress={openMenu}
              />
            </View>
          )
        : undefined,
    });
  }, [navigation, automation, t, openMenu, togglePause, s.detailHeaderActions]);

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

  const canEdit = automation.status !== "completed";
  const frequencyLabel = t(automationFrequencyMessageKey(automation.frequency));
  const scheduleLabel = formatAutomationScheduleDay(automation);
  const runDate = new Date(automation.next_run_at);
  const timeLabel = Number.isNaN(runDate.getTime())
    ? ""
    : runDate.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });

  const settingRow = (label: string, value: string, key: string) => (
    <Pressable
      key={key}
      style={s.detailSettingRow}
      onPress={openEditor}
      disabled={!canEdit}
      accessibilityRole={canEdit ? "button" : undefined}
      accessibilityLabel={`${label}, ${value}`}
    >
      <Text style={s.detailSettingLabel}>{label}</Text>
      <View style={s.detailSettingRight}>
        <Text style={s.detailSettingValue} numberOfLines={1}>
          {value}
        </Text>
        {canEdit ? <Icon name="chevron-forward" size={18} color={C.textTertiary} /> : null}
      </View>
    </Pressable>
  );

  return (
    <View style={s.root}>
      <View style={s.detailContent}>
        <View style={s.detailTaskCard}>
          <View style={s.detailTaskSection}>
            <Text style={s.detailTaskTitle}>{automationDisplayTitle(automation.prompt)}</Text>
          </View>
          <View style={s.detailDivider} />
          <View style={s.detailTaskSection}>
            <Text style={s.detailPrompt}>{automation.prompt}</Text>
          </View>
        </View>

        <View style={s.detailSettingsGroup}>
          {settingRow(t("automations.frequency_label"), frequencyLabel, "repeat")}
          <View style={s.detailDivider} />
          {settingRow(t("drawer.reminders"), scheduleLabel, "schedule")}
        </View>

        <View style={s.detailSettingsGroup}>
          {settingRow(t("automations.field_time"), timeLabel, "time")}
        </View>
      </View>

      {messages.length > 0 ? (
        <AutomationTranscript chatId={automation.chat_id} messages={messages} />
      ) : null}

      <AutomationActionsSheet
        visible={menuOpen}
        status={automation.status}
        hideTogglePause
        onClose={() => {
          if (isCurrent()) setMenuOpen(false);
        }}
        onEdit={() => {
          setMenuOpen(false);
          openEditor();
        }}
        onShare={() => {
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
