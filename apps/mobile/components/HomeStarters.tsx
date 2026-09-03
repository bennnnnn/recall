import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { useAuth } from "@/contexts/AuthContext";
import { useHome } from "@/contexts/HomeContext";
import { useTodos } from "@/contexts/TodosContext";
import type { HomeUrgentTodo } from "@/lib/api";
import { describeDueAt } from "@/lib/todos/dueDate";
import { instantHomePlaceholder, welcomeStarters } from "@/lib/homeWelcome";
import { filterHomeNudgeTodos } from "@/lib/homeReminderNudges";
import { firstOverdueHomeTodo, homeUrgentPrompt, listHomeUrgentTodos } from "@/lib/homeUrgentTodos";
import { tap } from "@/lib/haptics";
import { Space } from "@/lib/space";
import { Theme, useTheme, withAlpha } from "@/lib/theme";
import { Type } from "@/lib/type";

type Props = {
  onSelect: (prompt: string, chatId?: string) => void;
};

function OverdueReminderRow({
  todo,
  onSelect,
  onDismiss,
  styles: s,
  theme,
}: {
  todo: HomeUrgentTodo;
  onSelect: (prompt: string, chatId?: string) => void;
  onDismiss: (todoId: string) => void;
  styles: ReturnType<typeof makeStyles>;
  theme: Theme;
}) {
  const { t } = useTranslation();
  const due = describeDueAt(todo.due_at);

  return (
    <View style={s.urgentBlock}>
      <Text style={[s.sectionLabel, s.sectionLabelUrgent]}>{t("chat.home.overdue")}</Text>
      <View style={s.urgentCardWrap}>
        <Pressable
          style={[s.urgentCard, s.urgentCardOverdue]}
          onPress={() => {
            tap();
            onSelect(homeUrgentPrompt(todo, t));
          }}
          accessibilityRole="button"
          accessibilityLabel={todo.content}
        >
          <Icon name="alert-circle-outline" size={18} color={theme.danger} />
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
          <Icon name="chevron-forward" size={16} color={theme.danger} />
        </Pressable>
        <Pressable
          style={s.urgentDismiss}
          onPress={() => {
            tap();
            onDismiss(todo.id);
          }}
          hitSlop={14}
          accessibilityRole="button"
          accessibilityLabel={t("chat.home.dismiss_reminder")}
        >
          <Icon name="close" size={14} color={theme.textSecondary} />
        </Pressable>
      </View>
    </View>
  );
}

export function HomeStarters({ onSelect }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { user } = useAuth();
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

  return (
    <View style={s.wrap}>
      <Text style={s.greeting}>{display.greeting}</Text>

      {overdueTodo ? (
        <OverdueReminderRow
          todo={overdueTodo}
          onSelect={onSelect}
          onDismiss={(id) => void dismissReminderNudge(id)}
          styles={s}
          theme={theme}
        />
      ) : null}

      <View style={s.startersBlock}>
        <View style={s.chipRow}>
          {chips.map((starter, index) => (
            <Pressable
              key={`${starter.kind}-${index}-${starter.text}`}
              style={s.chip}
              onPress={() => {
                tap();
                onSelect(starter.prompt, starter.chat_id);
              }}
              accessibilityRole="button"
              accessibilityLabel={starter.text}
            >
              <Icon name="bulb-outline" size={14} color={theme.primary} />
              <Text style={s.chipText} numberOfLines={2}>
                {starter.text}
              </Text>
            </Pressable>
          ))}
        </View>
      </View>
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
      marginBottom: 8,
    },
    sectionLabelUrgent: {
      color: t.danger,
    },
    urgentBlock: { width: "100%", gap: 8, marginTop: 4 },
    urgentCardWrap: {
      position: "relative",
    },
    urgentCard: {
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      backgroundColor: t.dangerLight,
      borderRadius: 14,
      paddingHorizontal: 14,
      paddingVertical: 12,
      paddingRight: 36,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: withAlpha(t.danger, 0.22),
    },
    urgentDismiss: {
      position: "absolute",
      top: 6,
      right: 6,
      width: 24,
      height: 24,
      borderRadius: 12,
      backgroundColor: t.surface,
      alignItems: "center",
      justifyContent: "center",
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
    },
    urgentCardOverdue: {
      borderColor: t.danger,
    },
    urgentMain: { flex: 1, gap: 2 },
    urgentTitle: { ...Type.navTitle, color: t.text },
    urgentDue: { fontSize: 12, fontWeight: "600", color: t.danger },
    startersBlock: { width: "100%", marginTop: 4 },
    chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, justifyContent: "center" },
    chip: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
      backgroundColor: t.surfaceAlt,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      borderRadius: 999,
      paddingHorizontal: 14,
      paddingVertical: 10,
      minHeight: 44,
      maxWidth: "100%",
    },
    chipText: { ...Type.secondary, fontWeight: "500", color: t.text },
  });
}
