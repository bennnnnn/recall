import { useMemo } from "react";
import { Pressable, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { automationFrequencyMessageKey } from "@/components/automations/AutomationFrequencyPicker";
import { makeAutomationsStyles } from "@/components/automations/automationsStyles";
import type { Automation } from "@/lib/api";
import { automationDisplayTitle } from "@/lib/automations/schedule";
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
  const eyebrow = paused
    ? t("automations.status_paused")
    : completed
      ? t("automations.status_completed")
      : t("automations.title");

  return (
    <Pressable
      style={({ pressed }) => [
        s.card,
        paused && s.cardPaused,
        pressed && s.cardPressed,
      ]}
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
      <Text style={s.cardEyebrow}>{eyebrow}</Text>
      <Text style={s.cardTitle} numberOfLines={2}>
        {automationDisplayTitle(automation.prompt)}
      </Text>
      <Text style={s.cardDescription} numberOfLines={3}>
        {automation.prompt}
      </Text>

      <View style={s.cardDivider} />

      <Text style={s.cardFooter}>{frequencyLabel}</Text>
    </Pressable>
  );
}
