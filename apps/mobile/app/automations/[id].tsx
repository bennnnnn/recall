import { useCallback, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Alert, Platform, Pressable, ScrollView, Text, View } from "react-native";
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
import {
  type TimePreset,
  TIME_PRESETS,
  adjustDayOfMonth,
  adjustWeekday,
  applyTimePreset,
  describeLastRun,
  describeSchedule,
  describeTime,
  shareAutomation,
  timePresetLabel,
  weekdayOfNextRun,
} from "@/lib/automations/schedule";
import { IconSize } from "@/lib/icons";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { selection } from "@/lib/haptics";
import { useTheme } from "@/lib/theme";

type OpenField = "frequency" | "schedule" | "time" | null;

const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const DAY_OF_MONTH_OPTIONS = Array.from({ length: 28 }, (_, i) => i + 1);

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
      title: automation?.title || automation?.prompt || t("automations.title"),
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

  const toggleField = useCallback(
    (field: OpenField) => {
      if (!isEditable) return;
      if (openField === "time" && field !== "time" && pendingTime && automation) {
        if (pendingTime.getTime() !== new Date(automation.next_run_at).getTime()) {
          void update({ next_run_at: pendingTime.toISOString() });
        }
      }
      setOpenField((prev) => (prev === field ? null : field));
      setPendingTime(null);
    },
    [isEditable, openField, pendingTime, automation, update],
  );

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

  const onSelectWeekday = useCallback(
    (day: number) => {
      if (!automation) return;
      selection();
      const adjusted = adjustWeekday(automation.next_run_at, day);
      void update({ next_run_at: adjusted.toISOString() });
      closeFields();
    },
    [automation, update, closeFields],
  );

  const onSelectDayOfMonth = useCallback(
    (day: number) => {
      if (!automation) return;
      selection();
      const adjusted = adjustDayOfMonth(automation.next_run_at, day);
      void update({ next_run_at: adjusted.toISOString() });
      closeFields();
    },
    [automation, update, closeFields],
  );

  const onSelectTimePreset = useCallback(
    (preset: TimePreset) => {
      if (!automation) return;
      selection();
      if (preset === "custom") {
        setPendingTime(new Date(automation.next_run_at));
        setOpenField("time");
        return;
      }
      const adjusted = applyTimePreset(automation.next_run_at, preset);
      void update({ next_run_at: adjusted.toISOString() });
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

  const openRunHistory = useCallback(() => {
    if (!automation) return;
    setMenuOpen(false);
    router.push({ pathname: "/", params: { chatId: automation.chat_id } });
  }, [automation, router]);

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
  const scheduleLabel = describeSchedule(automation.frequency, automation.next_run_at);
  const timeLabel = describeTime(
    openField === "time" && pendingTime ? pendingTime.toISOString() : automation.next_run_at,
    t,
  );
  const isScheduleEditable =
    isEditable && (automation.frequency === "weekly" || automation.frequency === "monthly");
  const currentWeekday = weekdayOfNextRun(automation.next_run_at);

  return (
    <View style={s.root}>
      <ScrollView>
        {/* Title + Prompt card */}
        <View style={s.detailPromptCard}>
          <View style={s.detailTitleRow}>
            <Text style={s.detailTitle}>
              {automation.title || automation.prompt}
            </Text>
          </View>
          {automation.title ? (
            <View style={s.detailPromptRow}>
              <Text style={s.detailPrompt}>{automation.prompt}</Text>
            </View>
          ) : null}
        </View>

        {automation.status === "paused" ? (
          <View style={[s.cardStatusPill, s.cardStatusPillPaused, s.detailStatusPill]}>
            <Text style={[s.cardStatusPillText, s.cardStatusPillTextPaused]}>
              {t("automations.status_paused")}
            </Text>
          </View>
        ) : null}

        {/* Repeat / Schedule / Time / Last run card */}
        <View style={s.detailInfoCard}>
          {/* Repeat */}
          <Pressable
            style={[s.detailInfoRow, openField === "frequency" && s.detailInfoRowOpen]}
            onPress={() => toggleField("frequency")}
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

          {/* Schedule (day-of-week / day-of-month) */}
          {automation.status !== "completed" ? (
            <>
              <Pressable
                style={[
                  s.detailInfoRow,
                  s.detailInfoRowBorder,
                  openField === "schedule" && s.detailInfoRowOpen,
                ]}
                onPress={() => toggleField("schedule")}
                disabled={!isScheduleEditable}
                accessibilityRole={isScheduleEditable ? "button" : undefined}
                accessibilityLabel={`${t("automations.field_schedule")}, ${scheduleLabel}`}
                accessibilityState={{ expanded: openField === "schedule" }}
              >
                <Text style={s.detailInfoLabel}>{t("automations.field_schedule")}</Text>
                <View style={s.detailInfoValueGroup}>
                  <Text style={s.detailInfoValue}>{scheduleLabel}</Text>
                  {isScheduleEditable ? (
                    <Icon
                      name={openField === "schedule" ? "chevron-up" : "chevron-down"}
                      size={16}
                      color={C.textTertiary}
                    />
                  ) : null}
                </View>
              </Pressable>
              {openField === "schedule" && automation.frequency === "weekly" ? (
                <View style={s.detailPickerWrap}>
                  {WEEKDAY_LABELS.map((label, idx) => (
                    <Pressable
                      key={idx}
                      style={[s.detailInfoRow, idx === currentWeekday && s.detailInfoRowOpen]}
                      onPress={() => onSelectWeekday(idx)}
                      accessibilityRole="radio"
                      accessibilityState={{ selected: idx === currentWeekday }}
                    >
                      <Text
                        style={[
                          s.detailInfoLabel,
                          idx === currentWeekday && { color: C.primary, fontWeight: "600" },
                        ]}
                      >
                        {label}
                      </Text>
                      {idx === currentWeekday ? (
                        <Icon name="checkmark" size={18} color={C.primary} />
                      ) : null}
                    </Pressable>
                  ))}
                </View>
              ) : null}
              {openField === "schedule" && automation.frequency === "monthly" ? (
                <View style={s.detailPickerWrap}>
                  <ScrollView style={{ maxHeight: 200 }}>
                    {DAY_OF_MONTH_OPTIONS.map((day) => {
                      const current = new Date(automation.next_run_at).getDate();
                      const active = day === current;
                      return (
                        <Pressable
                          key={day}
                          style={[s.detailInfoRow, active && s.detailInfoRowOpen]}
                          onPress={() => onSelectDayOfMonth(day)}
                          accessibilityRole="radio"
                          accessibilityState={{ selected: active }}
                        >
                          <Text
                            style={[
                              s.detailInfoLabel,
                              active && { color: C.primary, fontWeight: "600" },
                            ]}
                          >
                            {day}
                          </Text>
                          {active ? <Icon name="checkmark" size={18} color={C.primary} /> : null}
                        </Pressable>
                      );
                    })}
                  </ScrollView>
                </View>
              ) : null}
            </>
          ) : null}

          {/* Time */}
          {automation.status !== "completed" ? (
            <>
              <Pressable
                style={[
                  s.detailInfoRow,
                  s.detailInfoRowBorder,
                  openField === "time" && s.detailInfoRowOpen,
                ]}
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
                  {TIME_PRESETS.map((p) => (
                    <Pressable
                      key={p.key}
                      style={s.detailInfoRow}
                      onPress={() => onSelectTimePreset(p.key)}
                      accessibilityRole="button"
                    >
                      <Text style={s.detailInfoLabel}>{timePresetLabel(p.key, t)}</Text>
                    </Pressable>
                  ))}
                  <Pressable
                    style={s.detailInfoRow}
                    onPress={() => onSelectTimePreset("custom")}
                    accessibilityRole="button"
                  >
                    <Text style={s.detailInfoLabel}>{timePresetLabel("custom", t)}</Text>
                  </Pressable>
                  {pendingTime ? (
                    <View style={{ paddingHorizontal: 16, paddingBottom: 8 }}>
                      <ReminderDateTimePicker
                        value={pendingTime}
                        onChange={onTimePickerChange}
                        disabled={saving}
                      />
                    </View>
                  ) : null}
                </View>
              ) : null}
            </>
          ) : null}

          {/* Last run */}
          <View style={[s.detailInfoRow, s.detailInfoRowBorder]}>
            <Text style={s.detailInfoLabel}>{t("automations.field_last_run")}</Text>
            <Text style={s.detailInfoValue}>{describeLastRun(automation, t)}</Text>
          </View>
        </View>
      </ScrollView>

      <AutomationActionsSheet
        visible={menuOpen}
        status={automation.status}
        chatId={automation.chat_id}
        hideTogglePause
        onClose={() => {
          if (isCurrent()) setMenuOpen(false);
        }}
        onEdit={() => {
          setMenuOpen(false);
          setEditOpen(true);
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
        onRunHistory={openRunHistory}
        onDelete={confirmDelete}
      />

      <AddAutomationSheet
        visible={editOpen}
        saving={saving}
        initial={{
          title: automation.title,
          prompt: automation.prompt,
          frequency: automation.frequency,
          nextRunAt: new Date(automation.next_run_at),
        }}
        onClose={() => {
          if (isCurrent()) setEditOpen(false);
        }}
        onSave={(title, prompt, frequency, nextRunAt) => {
          void update({ title, prompt, frequency, next_run_at: nextRunAt.toISOString() });
          setEditOpen(false);
        }}
      />
    </View>
  );
}
