import { useMemo } from "react";
import { Pressable, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { automationFrequencyMessageKey } from "@/components/automations/AutomationFrequencyPicker";
import { makeAutomationsStyles } from "@/components/automations/automationsStyles";
import type { Automation } from "@/lib/api";
import { describeLastRun, formatScheduleAt } from "@/lib/automations/schedule";
import { tap } from "@/lib/haptics";
import { useTheme } from "@/lib/theme";

export function AutomationCard({
  automation,
  onOpen,
  onLongPress,
}: {
  automation: Automation;
  onOpen: (id: string) => void;
  onLongPress: (automation: Automation) => void;
}) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeAutomationsStyles(C), [C]);
  const paused = automation.status === "paused";
  const completed = automation.status === "completed";
  const frequencyLabel = t(automationFrequencyMessageKey(automation.frequency));
  const lastRunLabel = describeLastRun(automation, t);
  const lastRunToneStyle = automation.last_run_status === "error" ? s.cardLastRunError : s.cardLastRunOk;

  const statusLabel = paused
    ? t("automations.status_paused")
    : completed
      ? t("automations.status_completed")
      : t("automations.status_active");
  const statusStyle = paused
    ? s.cardStatusLabelPaused
    : completed
      ? s.cardStatusLabelCompleted
      : s.cardStatusLabelActive;

  return (
    <Pressable
      style={[s.card, paused && s.cardPaused]}
      onPress={() => {
        tap();
        onOpen(automation.id);
      }}
      onLongPress={() => {
        tap();
        onLongPress(automation);
      }}
      accessibilityRole="button"
      accessibilityLabel={automation.title || automation.prompt}
    >
      <Text style={[s.cardStatusLabel, statusStyle]}>{statusLabel.toUpperCase()}</Text>
      {automation.title ? (
        <>
          <Text style={s.cardTitle} numberOfLines={1}>
            {automation.title}
          </Text>
          <Text style={s.cardPrompt} numberOfLines={2}>
            {automation.prompt}
          </Text>
        </>
      ) : (
        <Text style={s.cardPrompt} numberOfLines={3}>
          {automation.prompt}
        </Text>
      )}
      <Text style={s.cardMetaText}>
        {frequencyLabel}
        {!paused && !completed ? ` · ${formatScheduleAt(automation.next_run_at)}` : ""}
      </Text>
    </Pressable>
  );
}
