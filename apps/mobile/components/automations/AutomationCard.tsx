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
  const frequencyLabel = t(automationFrequencyMessageKey(automation.frequency));
  const lastRunLabel = describeLastRun(automation, t);
  const lastRunToneStyle = automation.last_run_status === "error" ? s.cardLastRunError : s.cardLastRunOk;

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
      accessibilityLabel={automation.prompt}
    >
      <Text style={s.cardPrompt} numberOfLines={2}>
        {automation.prompt}
      </Text>
      <View style={s.cardMetaRow}>
        {paused ? (
          <View style={[s.cardStatusPill, s.cardStatusPillPaused]}>
            <Text style={[s.cardStatusPillText, s.cardStatusPillTextPaused]}>
              {t("automations.status_paused")}
            </Text>
          </View>
        ) : (
          <Text style={s.cardMetaText}>
            {frequencyLabel} · {formatScheduleAt(automation.next_run_at)}
          </Text>
        )}
      </View>
      <Text style={[s.cardMetaText, lastRunToneStyle]} numberOfLines={1}>
        {lastRunLabel}
      </Text>
    </Pressable>
  );
}
