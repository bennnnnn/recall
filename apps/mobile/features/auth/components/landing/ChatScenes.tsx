/**
 * Landing scenes drawn as a chat: an everyday ask answered as a list, an equation worked
 * line by line to a checked answer, and a reminder made from one sentence, which, as in the
 * app, waits for its tap before it is added.
 */
import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Reveal, ReplyLine, SceneCard, UserBubble } from "./SceneParts";

type SceneProps = { active: boolean };

const TRIP_DAYS = ["onboarding.demo_trip_day1", "onboarding.demo_trip_day2", "onboarding.demo_trip_day3"];

export function ChatScene({ active }: SceneProps) {
  const { t } = useTranslation();
  return (
    <SceneCard>
      <Reveal active={active} step={0}>
        <UserBubble text={t("onboarding.demo_trip_ask")} />
      </Reveal>
      {TRIP_DAYS.map((key, index) => (
        <Reveal key={key} active={active} step={index + 1}>
          <ReplyLine text={`${index + 1}. ${t(key)}`} />
        </Reveal>
      ))}
    </SceneCard>
  );
}

/** "2x + 5 = 17" worked a line at a time; written in symbols, it reads the same in every language. */
const WORKING = ["2x = 17 − 5", "2x = 12", "x = 12 ÷ 2"];

export function HomeworkScene({ active }: SceneProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <SceneCard>
      <Reveal active={active} step={0}>
        <UserBubble text="2x + 5 = 17" />
      </Reveal>
      {WORKING.map((line, index) => (
        <Reveal key={line} active={active} step={index + 1}>
          <Text style={s.maths}>{line}</Text>
        </Reveal>
      ))}
      <Reveal active={active} step={WORKING.length + 1}>
        <View style={s.answer}>
          <Text style={s.answerValue}>x = 6</Text>
          <View style={s.checked}>
            <Icon name="check" size={IconSize.xs} color={theme.success} />
            <Text style={s.checkedText}>{t("onboarding.demo_checked")}</Text>
          </View>
        </View>
      </Reveal>
    </SceneCard>
  );
}

export function ReminderScene({ active }: SceneProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <SceneCard>
      <Reveal active={active} step={0}>
        <UserBubble text={t("onboarding.demo_remind_ask")} />
      </Reveal>
      <Reveal active={active} step={1} style={s.reminder}>
        <View style={s.reminderIcon}>
          <Icon name="bell" size={IconSize.sm} color={theme.primary} />
        </View>
        <View style={s.reminderText}>
          <Text style={s.reminderTitle}>{t("onboarding.demo_remind_title")}</Text>
          <Text style={s.reminderWhen}>{t("onboarding.demo_remind_when")}</Text>
        </View>
      </Reveal>
      <View>
        <Reveal active={active} step={2} style={s.addButton}>
          <Text style={s.addText}>{t("onboarding.demo_remind_add")}</Text>
        </Reveal>
        <View style={s.overlay} pointerEvents="none">
          <Reveal active={active} step={3} style={[s.addButton, s.added]}>
            <Icon name="check" size={IconSize.xs} color={theme.success} />
            <Text style={s.addedText}>{t("onboarding.demo_remind_added")}</Text>
          </Reveal>
        </View>
      </View>
    </SceneCard>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    maths: { ...Type.body, ...Weight.medium, color: theme.text, letterSpacing: 0.3 },
    answer: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      borderRadius: Radius.lg,
      borderWidth: 1.5,
      borderColor: theme.primary,
      backgroundColor: theme.primaryLight,
      paddingHorizontal: Space.gutter,
      paddingVertical: Space.sm,
      marginTop: Space.xs,
    },
    answerValue: { ...Type.title, color: theme.text },
    checked: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xxs,
      backgroundColor: theme.successLight,
      borderRadius: Radius.full,
      paddingHorizontal: Space.sm,
      paddingVertical: Space.xxs,
    },
    checkedText: { ...Type.caption, ...Weight.semibold, color: theme.success },
    reminder: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      borderRadius: Radius.lg,
      backgroundColor: theme.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      padding: Space.sm,
      marginTop: Space.xs,
    },
    reminderIcon: {
      width: 36,
      height: 36,
      borderRadius: Radius.md,
      backgroundColor: theme.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    reminderText: { flex: 1 },
    reminderTitle: { ...Type.body, ...Weight.semibold, color: theme.text },
    reminderWhen: { ...Type.caption, color: theme.textSecondary },
    addButton: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: Space.xxs,
      borderRadius: Radius.full,
      backgroundColor: theme.primary,
      paddingVertical: Space.sm,
    },
    addText: { ...Type.secondary, ...Weight.semibold, color: theme.onPrimary },
    // The confirmed state covers the button it replaces, as the tap in the app does.
    overlay: { position: "absolute", top: 0, left: 0, right: 0, bottom: 0 },
    added: { flex: 1, backgroundColor: theme.successLight },
    addedText: { ...Type.secondary, ...Weight.semibold, color: theme.success },
  });
}
