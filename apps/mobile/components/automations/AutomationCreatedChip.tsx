import { useMemo } from "react";
import { Pressable, StyleSheet, Text } from "react-native";
import { useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { automationFrequencyMessageKey } from "@/lib/automations/frequency";
import type { ParsedAutomationCreated } from "@/lib/parseAutomationCreated";
import { tap } from "@/lib/haptics";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Type } from "@/lib/type";
import { Theme, useTheme } from "@/lib/theme";

/** Confirmation chip after a chat-based ```automation create fence — tapping
 * it opens the My Job detail screen. Matches ChatGPT's "Mondays · Learn
 * Spanish" task chip; the fence itself is stripped from markdown.
 *
 * Self-navigating (no callback threaded through MessageBubble /
 * ChatMessageRow / useChatMessageList / index.tsx like `onOpenLesson`) —
 * unlike a lesson launch, opening My Job needs no chat-screen state, so
 * `useRouter` here keeps this a one-file addition instead of a five-file
 * prop chain. */
export function AutomationCreatedChip({ automation }: { automation: ParsedAutomationCreated }) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const router = useRouter();
  const frequencyLabel = t(automationFrequencyMessageKey(automation.frequency));

  return (
    <Pressable
      style={s.chip}
      onPress={() => {
        tap();
        router.push(`/automations/${automation.id}`);
      }}
      accessibilityRole="button"
      accessibilityLabel={`${frequencyLabel} · ${automation.prompt}`}
    >
      <Text style={s.frequency}>{frequencyLabel}</Text>
      <Text style={s.separator}> · </Text>
      <Text style={s.prompt} numberOfLines={1}>
        {automation.prompt}
      </Text>
    </Pressable>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    chip: {
      flexDirection: "row",
      alignItems: "center",
      alignSelf: "flex-start",
      marginTop: Space.sm,
      maxWidth: "100%",
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      borderRadius: Radius.full,
      borderWidth: 1,
      borderColor: C.border,
      backgroundColor: C.surface,
    },
    frequency: { ...Type.secondary, fontWeight: "700", color: C.primary },
    separator: { ...Type.secondary, color: C.textTertiary },
    prompt: { ...Type.secondary, color: C.text, flexShrink: 1 },
  });
}
