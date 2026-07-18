import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/contexts/AuthContext";
import { useHome } from "@/contexts/HomeContext";
import { useTodos } from "@/contexts/TodosContext";
import { api, type HomeUrgentTodo, type HomeProjectHighlight, type HomeStarter } from "@/lib/api";
import { queueChatLaunch } from "@/lib/chatLaunch";
import { buildHomeDailyQuizChatPrompt } from "@/lib/projectChat";
import { describeDueAt } from "@/lib/dueDate";
import { instantHomePlaceholder } from "@/lib/homeWelcome";
import { homeUrgentPrompt, listHomeUrgentTodos, partitionHomeUrgentTodos } from "@/lib/homeUrgentTodos";
import { learningProgressColors } from "@/lib/homeLearningCard";
import { selection, tap } from "@/lib/haptics";
import { Theme, useTheme, withAlpha } from "@/lib/theme";

type Props = {
  onSelect: (prompt: string) => void;
};

function starterIcon(kind: HomeStarter["kind"]): keyof typeof Ionicons.glyphMap {
  switch (kind) {
    case "time":
      return "time-outline";
    case "chat":
      return "chatbubble-ellipses-outline";
    case "memory":
      return "sparkles-outline";
    case "project":
      return "book-outline";
    default:
      return "bulb-outline";
  }
}

function ProjectHighlightCard({
  highlight,
  styles: s,
  theme,
}: {
  highlight: HomeProjectHighlight;
  styles: ReturnType<typeof makeStyles>;
  theme: Theme;
}) {
  const router = useRouter();
  const { t } = useTranslation();
  const completedToday =
    highlight.mastered_today + (highlight.missed_today ?? 0);
  const goal = highlight.daily_goal;
  const progressPct =
    goal > 0 ? Math.min(100, Math.round((completedToday / goal) * 100)) : 0;
  const label =
    highlight.kind === "trivia"
      ? t("chat.home.trivia_cue_continue", { done: completedToday, goal })
      : t("chat.home.vocab_cue_continue", { done: completedToday, goal });
  const colors = learningProgressColors({
    completedToday,
    dailyGoal: goal,
    surface: theme.surface,
    primaryLight: theme.primaryLight,
    dangerLight: theme.dangerLight,
    primary: theme.primary,
    danger: theme.danger,
  });

  const startDailyQuiz = () => {
    const variant = highlight.kind === "trivia" ? "trivia" : "vocab";
    queueChatLaunch(
      buildHomeDailyQuizChatPrompt(highlight),
      highlight.project_id,
      variant === "vocab" ? "en" : undefined,
      variant,
      "chat",
    );
    router.replace("/");
  };

  return (
    <Pressable
      style={[s.projectCard, { backgroundColor: colors.background }]}
      onPress={() => {
        tap();
        startDailyQuiz();
      }}
      accessibilityRole="button"
      accessibilityLabel={label}
    >
      <View style={s.projectMain}>
        <View style={s.projectLabelRow}>
          <Text style={s.projectProgressLabel} numberOfLines={1}>
            {label}
          </Text>
          <Ionicons name="chevron-forward" size={16} color={theme.textTertiary} />
        </View>
        <View style={[s.projectTrack, { backgroundColor: colors.track }]}>
          <View
            style={[
              s.projectFill,
              { width: `${progressPct}%`, backgroundColor: colors.fill },
            ]}
          />
        </View>
      </View>
    </Pressable>
  );
}

function UrgentTodoSection({
  label,
  todos,
  onSelect,
  onDismiss,
  styles: s,
  theme,
}: {
  label: string;
  todos: HomeUrgentTodo[];
  onSelect: (prompt: string) => void;
  onDismiss?: (todoId: string) => void;
  styles: ReturnType<typeof makeStyles>;
  theme: Theme;
}) {
  const { t } = useTranslation();

  return (
    <View style={s.urgentBlock}>
      <Text style={[s.sectionLabel, s.sectionLabelUrgent]}>{label}</Text>
      {todos.map((todo) => {
        const due = describeDueAt(todo.due_at);
        const overdue = todo.minutes_until < 0 || due?.tone === "overdue";
        return (
          <View key={todo.id} style={s.urgentCardWrap}>
            <Pressable
              style={[s.urgentCard, overdue && s.urgentCardOverdue]}
              onPress={() => {
                tap();
                onSelect(homeUrgentPrompt(todo, t));
              }}
              accessibilityRole="button"
              accessibilityLabel={todo.content}
            >
              <Ionicons
                name={overdue ? "alert-circle-outline" : "alarm-outline"}
                size={18}
                color={theme.danger}
              />
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
              <Ionicons name="chevron-forward" size={16} color={theme.danger} />
            </Pressable>
            {onDismiss ? (
              <Pressable
                style={s.urgentDismiss}
                onPress={() => {
                  tap();
                  onDismiss(todo.id);
                }}
                hitSlop={8}
                accessibilityRole="button"
                accessibilityLabel={t("chat.home.dismiss_reminder")}
              >
                <Ionicons name="close" size={14} color={theme.textSecondary} />
              </Pressable>
            ) : null}
          </View>
        );
      })}
    </View>
  );
}

export function HomeStarters({ onSelect }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { token, user } = useAuth();
  const { screen } = useHome();
  const {
    todos,
    loading: todosLoading,
    remindersReady,
    seenReminderIds,
    dismissReminderNudge,
  } = useTodos();
  const [dismissedStarterKeys, setDismissedStarterKeys] = useState<Set<string>>(
    () => new Set(),
  );
  const leadMinutes = user?.reminder_lead_minutes ?? undefined;
  // Never block first paint on /home — local greeting + starters, then hydrate.
  const display = screen ?? instantHomePlaceholder();

  const dismissStarter = async (starter: HomeStarter) => {
    const key = starter.id ?? starter.prompt;
    setDismissedStarterKeys((prev) => new Set(prev).add(key));
    if (starter.id && token) {
      try {
        await api.dismissSuggestion(token, starter.id);
      } catch {
        setDismissedStarterKeys((prev) => {
          const next = new Set(prev);
          next.delete(key);
          return next;
        });
      }
    }
  };

  const urgentTodos = useMemo(() => {
    // Wait until todos + seen-state are in sync. Silent refreshes used to paint
    // red urgent cards for a frame before seenReminderIds caught up.
    if (todosLoading || !remindersReady) return [];
    return listHomeUrgentTodos(todos, undefined, leadMinutes).filter(
      (todo) => !seenReminderIds.has(todo.id),
    );
  }, [todos, todosLoading, remindersReady, seenReminderIds, leadMinutes]);

  const urgentGroups = useMemo(() => partitionHomeUrgentTodos(urgentTodos), [urgentTodos]);

  const chips = display.starters
    .filter((starter) => starter.kind !== "todo")
    // No active learning → don't advertise learning chips that dump into an empty Projects screen.
    .filter((starter) => display.project_highlight != null || starter.kind !== "project")
    .filter((starter) => !dismissedStarterKeys.has(starter.id ?? starter.prompt));

  return (
    <View style={s.wrap}>
      <Text style={s.greeting}>{display.greeting}</Text>

      {display.project_highlight ? (
        <ProjectHighlightCard highlight={display.project_highlight} styles={s} theme={theme} />
      ) : null}

      {urgentGroups.overdue.length > 0 ? (
        <UrgentTodoSection
          label={t("chat.home.overdue")}
          todos={urgentGroups.overdue}
          onSelect={onSelect}
          onDismiss={(id) => void dismissReminderNudge(id)}
          styles={s}
          theme={theme}
        />
      ) : null}

      {urgentGroups.dueSoon.length > 0 ? (
        <UrgentTodoSection
          label={t("chat.home.due_soon")}
          todos={urgentGroups.dueSoon}
          onSelect={onSelect}
          styles={s}
          theme={theme}
        />
      ) : null}

      {chips.length > 0 ? (
        <View style={s.startersBlock}>
          <Text style={s.sectionLabel}>{t("chat.home.for_you")}</Text>
          <View style={s.chipRow}>
            {chips.map((starter, index) => (
              <Pressable
                key={`${starter.kind}-${index}-${starter.text}`}
                style={s.chip}
                onPress={() => {
                  tap();
                  onSelect(starter.prompt);
                }}
                onLongPress={() => {
                  selection();
                  void dismissStarter(starter);
                }}
                accessibilityRole="button"
                accessibilityLabel={starter.text}
                accessibilityHint={t("chat.home.dismiss_suggestion")}
              >
                <Ionicons
                  name={starterIcon(starter.kind)}
                  size={14}
                  color={theme.primary}
                />
                <Text style={s.chipText} numberOfLines={2}>
                  {starter.text}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>
      ) : null}
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: { width: "100%", paddingHorizontal: 20, gap: 12 },
    greeting: {
      fontSize: 26,
      fontWeight: "800",
      color: t.text,
      textAlign: "center",
      letterSpacing: -0.5,
    },
    projectCard: {
      width: "100%",
      borderRadius: 14,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      paddingVertical: 12,
      paddingHorizontal: 14,
      marginTop: 4,
    },
    projectMain: { gap: 8 },
    projectLabelRow: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 8,
    },
    projectProgressLabel: {
      flex: 1,
      fontSize: 14,
      fontWeight: "700",
      color: t.text,
    },
    projectTrack: {
      height: 4,
      borderRadius: 2,
      overflow: "hidden",
    },
    projectFill: { height: 4, borderRadius: 2 },
    sectionLabel: {
      fontSize: 11,
      fontWeight: "700",
      color: t.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.8,
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
      borderWidth: 1,
      borderColor: withAlpha(t.danger, 0.25),
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
      borderWidth: 1.5,
    },
    urgentMain: { flex: 1, gap: 2 },
    urgentTitle: { fontSize: 15, fontWeight: "700", color: t.text },
    urgentDue: { fontSize: 12, fontWeight: "600", color: t.danger },
    startersBlock: { width: "100%", marginTop: 4 },
    chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, justifyContent: "center" },
    chip: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
      backgroundColor: t.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      borderRadius: 999,
      paddingHorizontal: 14,
      paddingVertical: 10,
      maxWidth: "100%",
    },
    chipText: { fontSize: 14, fontWeight: "600", color: t.text },
  });
}
