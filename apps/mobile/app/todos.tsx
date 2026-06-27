import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Redirect } from "expo-router";
import { useFocusEffect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { C } from "@/constants/Colors";
import { useAuth } from "@/contexts/AuthContext";
import { api, Todo } from "@/lib/api";

export default function TodosScreen() {
  const { token, user } = useAuth();
  const { t } = useTranslation();
  const insets = useSafeAreaInsets();
  const [loading, setLoading] = useState(true);
  const [todos, setTodos] = useState<Todo[]>([]);
  const [input, setInput] = useState("");

  const [error, setError] = useState(false);

  if (!token) return <Redirect href="/login" />;

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const items = await api.listTodos(token);
      setTodos(items);
      setError(false);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  const handleAdd = async () => {
    const text = input.trim();
    if (!text || !token) return;
    setInput("");
    try {
      const created = await api.createTodo(token, text);
      setTodos((prev) => [created, ...prev]);
    } catch {
      Alert.alert(t("todos.error"), t("todos.error_create"));
    }
  };

  const handleToggle = async (todo: Todo) => {
    if (!token) return;
    const original = [...todos];
    setTodos((prev) =>
      prev.map((t) => (t.id === todo.id ? { ...t, checked: !t.checked } : t)),
    );
    try {
      await api.updateTodo(token, todo.id, { checked: !todo.checked });
    } catch {
      setTodos(original);
    }
  };

  const handleDelete = (todo: Todo) => {
    Alert.alert(t("todos.delete_confirm"), `"${todo.content}"`, [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("common.delete"),
        style: "destructive",
        onPress: async () => {
          if (!token) return;
          setTodos((prev) => prev.filter((t) => t.id !== todo.id));
          try {
            await api.deleteTodo(token, todo.id);
          } catch {
            void load();
          }
        },
      },
    ]);
  };

  const unchecked = todos.filter((t) => !t.checked);
  const checked = todos.filter((t) => t.checked);

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator size="large" color={C.primary} />
      </View>
    );
  }

  return (
    <View style={s.root}>
      {/* Add input */}
      <View style={s.inputBar}>
        <TextInput
          style={s.input}
          placeholder={t("todos.placeholder")}
          placeholderTextColor={C.textTertiary}
          value={input}
          onChangeText={setInput}
          onSubmitEditing={handleAdd}
          returnKeyType="done"
          maxLength={500}
        />
        <Pressable
          style={[s.addBtn, !input.trim() && s.addBtnDisabled]}
          onPress={handleAdd}
          disabled={!input.trim()}
          hitSlop={6}
        >
          <Ionicons
            name="add"
            size={22}
            color={input.trim() ? C.primary : C.textTertiary}
          />
        </Pressable>
      </View>

      <View style={s.list}>
        {error ? (
          <View style={s.empty}>
            <Ionicons
              name="cloud-offline-outline"
              size={48}
              color={C.textTertiary}
              style={s.emptyIcon}
            />
            <Text style={s.emptyTitle}>{t("common.error")}</Text>
            <Pressable style={s.retryBtn} onPress={() => { setLoading(true); void load(); }}>
              <Text style={s.retryText}>{t("common.retry")}</Text>
            </Pressable>
          </View>
        ) : todos.length === 0 ? (
          <View style={s.empty}>
            <Ionicons
              name="checkbox-outline"
              size={48}
              color={C.primary}
              style={s.emptyIcon}
            />
            <Text style={s.emptyTitle}>{t("todos.empty_title")}</Text>
            <Text style={s.emptyBody}>{t("todos.empty_body")}</Text>
          </View>
        ) : (
          <>
            {unchecked.map((todo) => (
              <TodoRow
                key={todo.id}
                todo={todo}
                onToggle={() => handleToggle(todo)}
                onDelete={() => handleDelete(todo)}
              />
            ))}
            {checked.length > 0 && (
              <>
                <Text style={s.sectionLabel}>
                  {t("todos.done")} ({checked.length})
                </Text>
                {checked.map((todo) => (
                  <TodoRow
                    key={todo.id}
                    todo={todo}
                    onToggle={() => handleToggle(todo)}
                    onDelete={() => handleDelete(todo)}
                  />
                ))}
              </>
            )}
          </>
        )}
      </View>
    </View>
  );
}

function TodoRow({
  todo,
  onToggle,
  onDelete,
}: {
  todo: Todo;
  onToggle: () => void;
  onDelete: () => void;
}) {
  return (
    <View style={s.todoRow}>
      <Pressable onPress={onToggle} hitSlop={10} style={s.checkbox}>
        <Ionicons
          name={todo.checked ? "checkbox" : "square-outline"}
          size={22}
          color={todo.checked ? C.primary : C.textTertiary}
        />
      </Pressable>
      <Text
        style={[s.todoText, todo.checked && s.todoDone]}
        selectable
        numberOfLines={4}
      >
        {todo.content}
      </Text>
      <Pressable onPress={onDelete} hitSlop={8}>
        <Ionicons name="trash-outline" size={16} color={C.textTertiary} />
      </Pressable>
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: C.bg },
  inputBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.border,
  },
  input: {
    flex: 1,
    fontSize: 16,
    color: C.text,
    backgroundColor: C.surface,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: C.border,
  },
  addBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: C.surface,
  },
  addBtnDisabled: { opacity: 0.5 },
  list: { flex: 1 },
  todoRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.border,
  },
  checkbox: { padding: 2 },
  todoText: { flex: 1, fontSize: 16, lineHeight: 22, color: C.text },
  todoDone: {
    color: C.textTertiary,
    textDecorationLine: "line-through",
  },
  sectionLabel: {
    fontSize: 13,
    fontWeight: "600",
    color: C.textSecondary,
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 4,
  },
  empty: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingTop: 80,
    paddingHorizontal: 32,
  },
  emptyIcon: { opacity: 0.5, marginBottom: 16 },
  emptyTitle: { fontSize: 17, fontWeight: "700", color: C.text, marginBottom: 6 },
  emptyBody: { fontSize: 14, color: C.textSecondary, textAlign: "center", lineHeight: 20 },
  retryBtn: {
    marginTop: 16,
    paddingHorizontal: 20,
    paddingVertical: 8,
    borderRadius: 10,
    backgroundColor: C.primary,
  },
  retryText: { fontSize: 14, fontWeight: "600", color: "#fff" },
});
