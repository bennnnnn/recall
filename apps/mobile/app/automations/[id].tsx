import { useCallback, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Alert, Platform, Pressable, Text, View } from "react-native";
import type { DateTimePickerEvent } from "@react-native-community/datetimepicker";
import { Redirect, useLocalSearchParams, useNavigation, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { AddAutomationSheet } from "@/components/automations/AddAutomationSheet";
import { AutomationActionsSheet } from "@/components/automations/AutomationActionsSheet";
import {
  AutomationFrequencyPicker,
  automationFrequencyMessageKey,
} from "@/components/automations/AutomationFrequencyPicker";
import { makeAutomationsStyles } from "@/components/automations/automationsStyles";
import { Icon } from "@/components/Icon";
import { IconButton } from "@/components/IconButton";
import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { ReminderDateTimePicker } from "@/components/todos/ReminderDateTimePicker";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useAuth } from "@/contexts/AuthContext";
import { useAutomationDetail } from "@/hooks/useAutomationDetail";
import type { AutomationFrequency } from "@/lib/api";
import { describeLastRun, formatScheduleAt, shareAutomation } from "@/lib/automations/schedule";
import { IconSize } from "@/lib/icons";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { useTheme } from "@/lib/theme";

type OpenField = "frequency" | "time" | null;

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
  const [openField, setOpenField] = useState<OpenField>(null);
  const [pendingTime, setPendingTime] = useState<Date | null>(null);
  const sharing = useRef(false);
  const isEditable = automation != null && automation.status !== "completed" && !saving;

  const openMenu = useCallback(() => {
    if (isCurrent()) setMenuOpen(true);
  }, [isCurrent]);

  useLayoutEffect(() => {
    navigation.setOptions({
      title: automation ? automation.prompt : t("automations.title"),
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
                name="ellipsis-horizontal"
                size={IconSize.md}
                accessibilityLabel={t("automations.menu_a11y")}
                onPress={openMenu}
              />
            </View>
          )
        : undefined,
    });
  }, [navigation, automation, t, openMenu, togglePause, s.detailHeaderActions]);

  const closeFields = useCallback(() => {
    setOpenField(null);
    setPendingTime(null);
  }, []);

  const toggleFrequencyField = useCallback(() => {
    if (!isEditable) return;
    setOpenField((field) => (field === "frequency" ? null : "frequency"));
  }, [isEditable]);

  const toggleTimeField = useCallback(() => {
    if (!isEditable || !automation) return;
    if (openField === "time") {
      if (pendingTime && pendingTime.getTime() !== new Date(automation.next_run_at).getTime()) {
        void update({ next_run_at: pendingTime.toISOString() });
      }
      closeFields();
      return;
    }
    setPendingTime(new Date(automation.next_run_at));
    setOpenField("time");
  }, [isEditable, automation, openField, pendingTime, update, closeFields]);

  const onSelectFrequency = useCallback(
    (frequency: AutomationFrequency) => {
      if (automation && frequency !== automation.frequency) void update({ frequency });
      closeFields();
    },
    [automation, update, closeFields],
  );

  const onTimePickerChange = useCallback(
    (event: DateTimePickerEvent, date?: Date) => {
      if (!automation) return;
      if (Platform.OS === "android") {
        closeFields();
        if (event.type === "dismissed" || !date) return;
        if (date.getTime() !== new Date(automation.next_run_at).getTime()) {
          void update({ next_run_at: date.toISOString() });
        }
        return;
      }
      if (date) setPendingTime(date);
    },
    [automation, update, closeFields],
  );

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

  const frequencyLabel =
    automation.status === "completed"
      ? t("automations.status_completed")
      : t(automationFrequencyMessageKey(automation.frequency));
  const timeLabel = formatScheduleAt(
    openField === "time" && pendingTime ? pendingTime.toISOString() : automation.next_run_at,
  );

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
        <Pressable
          style={[s.detailInfoRow, openField === "frequency" && s.detailInfoRowOpen]}
          onPress={toggleFrequencyField}
          disabled={!isEditable}
          accessibilityRole={isEditable ? "button" : undefined}
          accessibilityLabel={`${t("automations.frequency_label")}, ${frequencyLabel}`}
          accessibilityState={{ expanded: openField === "frequency" }}
        >
          <Text style={s.detailInfoLabel}>{t("automations.frequency_label")}</Text>
          <View style={s.detailInfoValueGroup}>
            <Text style={s.detailInfoValue}>{frequencyLabel}</Text>
            {isEditable ? (
              <Icon
                name={openField === "frequency" ? "chevron-up" : "chevron-down"}
                size={16}
                color={C.textTertiary}
              />
            ) : null}
          </View>
        </Pressable>
        {openField === "frequency" ? (
          <View style={s.detailPickerWrap}>
            <AutomationFrequencyPicker selected={automation.frequency} onSelect={onSelectFrequency} />
          </View>
        ) : null}

        {automation.status !== "completed" ? (
          <>
            <Pressable
              style={[s.detailInfoRow, s.detailInfoRowBorder, openField === "time" && s.detailInfoRowOpen]}
              onPress={toggleTimeField}
              disabled={!isEditable}
              accessibilityRole={isEditable ? "button" : undefined}
              accessibilityLabel={`${t("automations.field_time")}, ${timeLabel}`}
              accessibilityState={{ expanded: openField === "time" }}
            >
              <Text style={s.detailInfoLabel}>{t("automations.field_time")}</Text>
              <View style={s.detailInfoValueGroup}>
                <Text style={s.detailInfoValue}>{timeLabel}</Text>
                {isEditable ? (
                  <Icon
                    name={openField === "time" ? "chevron-up" : "chevron-down"}
                    size={16}
                    color={C.textTertiary}
                  />
                ) : null}
              </View>
            </Pressable>
            {openField === "time" ? (
              <View style={s.detailPickerWrap}>
                <ReminderDateTimePicker
                  value={pendingTime ?? new Date(automation.next_run_at)}
                  onChange={onTimePickerChange}
                  disabled={saving}
                />
              </View>
            ) : null}
          </>
        ) : null}

        <View style={[s.detailInfoRow, s.detailInfoRowBorder]}>
          <Text style={s.detailInfoLabel}>{t("automations.field_last_run")}</Text>
          <Text style={s.detailInfoValue}>{describeLastRun(automation, t)}</Text>
        </View>
      </View>

      <AutomationActionsSheet
        visible={menuOpen}
        status={automation.status}
        hideTogglePause
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
