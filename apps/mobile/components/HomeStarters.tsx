import { useMemo, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/contexts/AuthContext";
import { useHome } from "@/contexts/HomeContext";
import { useTodos } from "@/contexts/TodosContext";
import { api, type HomeUrgentTodo, type HomeProjectHighlight, type HomeStarter } from "@/lib/api";
import { describeDueAt } from "@/lib/dueDate";
import { homeUrgentPrompt, homeUrgentSubtitle, listHomeUrgentTodos, partitionHomeUrgentTodos } from "@/lib/homeUrgentTodos";
import { Theme, useTheme } from "@/lib/theme";

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

  return (
    <Pressable
      style={s.projectCard}
      onPress={() => router.push(`/projects/${highlight.project_id}`)}
    >
      <View style={s.projectIconWrap}>
        <Ionicons name="language-outline" size={20} color={theme.primary} />
      </View>
      <Text style={s.projectTitle} numberOfLines={1}>
        {highlight.title}
      </Text>
      <Ionicons name="chevron-forward" size={18} color={theme.textTertiary} />
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
              onPress={() => onSelect(homeUrgentPrompt(todo))}
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
                onPress={() => onDismiss(todo.id)}
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
  const { screen, loading } = useHome();
  const { todos, loading: todosLoading, seenReminderIds, dismissReminderNudge } = useTodos();
  const [dismissedStarterKeys, setDismissedStarterKeys] = useState<Set<string>>(
    () => new Set(),
  );
  const leadMinutes = user?.reminder_lead_minutes ?? undefined;

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
    const raw =
      !todosLoading ? listHomeUrgentTodos(todos, undefined, leadMinutes) : (screen?.urgent_todos ?? []);
    return raw.filter((todo) => !seenReminderIds.has(todo.id));
  }, [todos, todosLoading, screen?.urgent_todos, seenReminderIds, leadMinutes]);

  const urgentGroups = useMemo(() => partitionHomeUrgentTodos(urgentTodos), [urgentTodos]);

  const displaySubtitle = useMemo(() => {
    if (screen?.project_highlight) return null;
    if (!todosLoading) {
      const fromUrgent = homeUrgentSubtitle(urgentTodos);
      if (fromUrgent) return fromUrgent;
      if ((screen?.urgent_todos.length ?? 0) > 0 && urgentTodos.length === 0) {
        return null;
      }
    }
    return screen?.subtitle ?? null;
  }, [
    screen?.project_highlight,
    todosLoading,
    urgentTodos,
    screen?.subtitle,
    screen?.urgent_todos.length,
  ]);

  if (loading && !screen) {
    return (
      <View style={s.loadingWrap}>
        <ActivityIndicator color={theme.primary} />
      </View>
    );
  }

  if (!screen) {
    return (
      <View style={s.loadingWrap}>
        <Text style={s.greeting}>{t("chat.empty_title")}</Text>
      </View>
    );
  }

  const chips = screen.starters
    .filter((starter) => starter.kind !== "todo")
    .filter((starter) => !dismissedStarterKeys.has(starter.id ?? starter.prompt));

  return (
    <View style={s.wrap}>
      <Text style={s.greeting}>{screen.greeting}</Text>
      {displaySubtitle ? <Text style={s.subtitle}>{displaySubtitle}</Text> : null}

      {screen.project_highlight ? (
        <ProjectHighlightCard highlight={screen.project_highlight} styles={s} theme={theme} />
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
                onPress={() => onSelect(starter.prompt)}
                onLongPress={() => void dismissStarter(starter)}
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
    loadingWrap: { paddingVertical: 24, alignItems: "center" },
    greeting: {
      fontSize: 26,
      fontWeight: "800",
      color: t.text,
      textAlign: "center",
      letterSpacing: -0.5,
    },
    subtitle: {
      fontSize: 15,
      lineHeight: 22,
      color: t.textSecondary,
      textAlign: "center",
      paddingHorizontal: 8,
    },
    projectCard: {
      width: "100%",
      flexDirection: "row",
      alignItems: "center",
      gap: 12,
      backgroundColor: t.surface,
      borderRadius: 16,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      padding: 14,
      marginTop: 4,
    },
    projectIconWrap: {
      width: 40,
      height: 40,
      borderRadius: 12,
      backgroundColor: t.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    projectTitle: { flex: 1, fontSize: 17, fontWeight: "700", color: t.text },
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
      borderColor: t.danger + "40",
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
