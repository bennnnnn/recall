import { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { Icon } from "@/ui/icons/Icon";
import { Chip } from "@/ui/controls/Chip";
import { useAuth } from "@/contexts/AuthContext";
import { useComposerDraftActivity } from "@/contexts/ComposerDraftContext";
import { useHome } from "@/features/home/context/HomeContext";
import { useTodos } from "@/features/todos/context/TodosContext";
import type { HomeUrgentTodo } from "@/lib/api";
import { describeDueAt } from "@/features/todos/model/dueDate";
import { instantHomePlaceholder, welcomeStarterIcon, welcomeStarters } from "@/features/home/model/homeWelcome";
import { filterHomeNudgeTodos } from "@/features/todos/model/homeReminderNudges";
import { firstOverdueHomeTodo, listHomeUrgentTodos } from "@/features/todos/model/homeUrgentTodos";
import { tap } from "@/lib/haptics";
import { isHomeGuidanceRetired, retireHomeGuidance } from "@/features/home/model/homeGuidancePrefs";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme, withAlpha } from "@/lib/theme";
import { IconSize } from "@/ui/icons/sizes";
import { Type, Weight } from "@/lib/type";

type Props = {
  onSelect: (prompt: string, chatId?: string) => void;
};

function OverdueReminderRow({
  todo,
  onDismiss,
  styles: s,
  theme,
}: {
  todo: HomeUrgentTodo;
  onDismiss: (todoId: string) => void;
  styles: ReturnType<typeof makeStyles>;
  theme: Theme;
}) {
  const { t } = useTranslation();
  const router = useRouter();
  const due = describeDueAt(todo.due_at);

  return (
    <View style={s.urgentBlock}>
      <Text style={[s.sectionLabel, s.sectionLabelUrgent]}>{t("chat.home.overdue")}</Text>
      <View style={s.urgentCardWrap}>
        <Pressable
          style={[s.urgentCard, s.urgentCardOverdue]}
          onPress={() => {
            tap();
            // Same target as a due-reminder push: Schedule with the row lit up.
            router.push({
              pathname: "/todos",
              params: { highlight: todo.id },
            });
          }}
          accessibilityRole="button"
          accessibilityLabel={todo.content}
        >
              <Icon name="alert-circle" size={IconSize.sm} color={theme.warning} />
          <View style={s.urgentMain}>
            <Text style={s.urgentTitle} numberOfLines={2}>
              {todo.content}
            </Text>
            {due ? (
              <Text style={s.urgentDue} numberOfLines={1}>
                {due.label}
              </Text>
            ) : null}
          </View>
          <Icon name="chevron-right" size={IconSize.xs} color={theme.warning} />
        </Pressable>
        <Pressable
          style={s.urgentDismiss}
          onPress={() => {
            tap();
            onDismiss(todo.id);
          }}
          accessibilityRole="button"
          accessibilityLabel={t("chat.home.dismiss_reminder")}
        >
          <View style={s.urgentDismissCircle}>
            <Icon name="close" size={IconSize.xxs} color={theme.textSecondary} />
          </View>
        </Pressable>
      </View>
    </View>
  );
}

export function HomeStarters({ onSelect }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { user } = useAuth();
  const composerActive = useComposerDraftActivity();
  const [guidanceRetired, setGuidanceRetired] = useState<boolean | null>(null);
  const { screen } = useHome();
  const {
    todos,
    loading: todosLoading,
    remindersReady,
    homeNudgeDismissed,
    dismissReminderNudge,
  } = useTodos();
  const leadMinutes = user?.reminder_lead_minutes ?? undefined;
  // Never block first paint on /home — local greeting, then hydrate the name.
  const display = screen ?? instantHomePlaceholder();
  const chips = welcomeStarters();

  useEffect(() => {
    let current = true;
    if (!user?.id) {
      setGuidanceRetired(false);
      return () => {
        current = false;
      };
    }
    setGuidanceRetired(null);
    void isHomeGuidanceRetired(user.id).then((retired) => {
      if (current) setGuidanceRetired(retired);
    });
    return () => {
      current = false;
    };
  }, [user?.id]);

  useEffect(() => {
    if (!composerActive || guidanceRetired !== false) return;
    setGuidanceRetired(true);
    if (user?.id) void retireHomeGuidance(user.id);
  }, [composerActive, guidanceRetired, user?.id]);

  const overdueTodo = useMemo(() => {
    // Wait until todos + nudge-state are in sync. Silent refreshes used to paint
    // red urgent cards for a frame before persisted dismissals caught up.
    if (todosLoading || !remindersReady) return undefined;
    const urgent = listHomeUrgentTodos(todos, undefined, leadMinutes);
    return firstOverdueHomeTodo(
      filterHomeNudgeTodos(urgent, { dismissed: homeNudgeDismissed }),
    );
  }, [
    todos,
    todosLoading,
    remindersReady,
    homeNudgeDismissed,
    leadMinutes,
  ]);

  // Once typing begins, leave the empty-chat canvas clear and focused.
  if (composerActive) return null;

  return (
    <View style={s.wrap}>
      <Text style={s.greeting}>{display.greeting}</Text>

      {overdueTodo ? (
        <OverdueReminderRow
          todo={overdueTodo}
          onDismiss={(id) => void dismissReminderNudge(id)}
          styles={s}
          theme={theme}
        />
      ) : null}

      {guidanceRetired === false ? (
        <View style={s.startersBlock}>
          <View style={s.chipRow}>
            {chips.map((starter, index) => (
              <Chip
                key={`${starter.kind}-${index}-${starter.text}`}
                label={starter.text}
                icon={welcomeStarterIcon(index)}
                numberOfLines={2}
                onPress={() => {
                  setGuidanceRetired(true);
                  if (user?.id) void retireHomeGuidance(user.id);
                  tap();
                  onSelect(starter.prompt, starter.chat_id);
                }}
              />
            ))}
          </View>
        </View>
      ) : null}
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: { width: "100%", paddingHorizontal: Space.gutter, gap: Space.sm },
    greeting: {
      ...Type.display,
      color: t.text,
      textAlign: "center",
      letterSpacing: -0.4,
    },
    sectionLabel: {
      ...Type.overline,
      color: t.textTertiary,
      marginBottom: Space.xs,
    },
    sectionLabelUrgent: {
      color: t.warning,
    },
    urgentBlock: { width: "100%", gap: Space.xs, marginTop: Space.xxs },
    urgentCardWrap: {
      position: "relative",
    },
    urgentCard: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      backgroundColor: withAlpha(t.warning, 0.12),
      borderRadius: Radius.lg,
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      paddingRight: 36,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: withAlpha(t.warning, 0.28),
    },
    urgentDismiss: {
      position: "absolute",
      // 44×44 touch target; negative offsets keep the visible 24px circle at
      // its old center (top 6 + 12).
      top: -4,
      right: -4,
      width: Space.minTouch,
      height: Space.minTouch,
      alignItems: "center",
      justifyContent: "center",
    },
    urgentDismissCircle: {
      width: Space.lg,
      height: Space.lg,
      borderRadius: Radius.md,
      backgroundColor: t.surface,
      alignItems: "center",
      justifyContent: "center",
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
    },
    urgentCardOverdue: {
      borderColor: t.warning,
    },
    urgentMain: { flex: 1, gap: 2 },
    urgentTitle: { ...Type.navTitle, color: t.text },
    urgentDue: { ...Type.caption, ...Weight.semibold, color: t.warning },
    startersBlock: { width: "100%", marginTop: Space.xxs },
    chipRow: { flexDirection: "row", flexWrap: "wrap", gap: Space.xs, justifyContent: "center" },
  });
}
