import { useCallback, useMemo, useState } from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import DraggableFlatList, {
  type RenderItemParams,
  ScaleDecorator,
} from "react-native-draggable-flatlist";
import { useTranslation } from "react-i18next";

import { Theme, useTheme } from "@/lib/theme";
import type { Todo } from "@/lib/api";
import type { ListGroup } from "@/lib/listGroups";

type Props = {
  groups: ListGroup[];
  initialExpandedTopic?: string;
  togglingId: string | null;
  onReorderGroups: (topics: string[]) => void;
  onReorderItems: (topic: string, ordered: Todo[]) => void;
  onToggle: (todo: Todo) => void;
  onDelete: (todo: Todo) => void;
  onAddItem: (topic: string, text: string) => void;
  onDeleteGroup: (topic: string, title: string) => void;
};

export function ListGroupsView({
  groups,
  initialExpandedTopic,
  togglingId,
  onReorderGroups,
  onReorderItems,
  onToggle,
  onDelete,
  onAddItem,
  onDeleteGroup,
}: Props) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const [collapsed, setCollapsed] = useState<Set<string>>(() => {
    if (!initialExpandedTopic) return new Set<string>();
    const expanded = initialExpandedTopic.trim().toLowerCase();
    return new Set(
      groups
        .map((group) => group.topic)
        .filter((topic) => topic.toLowerCase() !== expanded),
    );
  });
  const [draftByTopic, setDraftByTopic] = useState<Record<string, string>>({});

  const toggleCollapsed = useCallback((topic: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(topic)) next.delete(topic);
      else next.add(topic);
      return next;
    });
  }, []);

  const renderGroup = useCallback(
    ({ item: group, drag, isActive }: RenderItemParams<ListGroup>) => {
      const isCollapsed = collapsed.has(group.topic);
      const draft = draftByTopic[group.topic] ?? "";

      return (
        <ScaleDecorator>
          <View style={[s.group, isActive && s.groupDragging]}>
            <View style={s.groupHeader}>
              <Pressable onLongPress={drag} delayLongPress={120} hitSlop={8} style={s.dragHandle}>
                <Ionicons name="reorder-three" size={22} color={C.textTertiary} />
              </Pressable>
              <Pressable
                style={s.groupHeaderMain}
                onPress={() => toggleCollapsed(group.topic)}
              >
                <Ionicons
                  name={isCollapsed ? "chevron-forward" : "chevron-down"}
                  size={16}
                  color={C.textSecondary}
                />
                <Text style={s.groupTitle}>{group.title}</Text>
                <Text style={s.groupCount}>
                  {group.open.length > 0
                    ? t("lists.open_count", { count: group.open.length })
                    : t("lists.group_empty")}
                </Text>
              </Pressable>
              {!group.isDefault ? (
                <Pressable
                  hitSlop={8}
                  onPress={() => onDeleteGroup(group.topic, group.title)}
                >
                  <Ionicons name="trash-outline" size={18} color={C.textTertiary} />
                </Pressable>
              ) : null}
            </View>

            {!isCollapsed ? (
              <>
                {group.open.length > 0 ? (
                  <DraggableFlatList
                    data={group.open}
                    keyExtractor={(todo) => todo.id}
                    scrollEnabled={false}
                    onDragEnd={({ data }) => onReorderItems(group.topic, data)}
                    renderItem={({
                      item: todo,
                      drag: dragItem,
                      isActive: itemActive,
                    }) => (
                      <ScaleDecorator>
                        <ListItemRow
                          todo={todo}
                          busy={togglingId === todo.id}
                          dragging={itemActive}
                          onDrag={dragItem}
                          onToggle={() => onToggle(todo)}
                          onDelete={() => onDelete(todo)}
                        />
                      </ScaleDecorator>
                    )}
                  />
                ) : (
                  <Text style={s.groupHint}>{t("lists.group_add_hint")}</Text>
                )}

                <View style={s.inlineAddRow}>
                  <TextInput
                    style={s.inlineInput}
                    placeholder={t("lists.item_placeholder")}
                    placeholderTextColor={C.textTertiary}
                    value={draft}
                    onChangeText={(text) =>
                      setDraftByTopic((prev) => ({ ...prev, [group.topic]: text }))
                    }
                    onSubmitEditing={() => {
                      const text = draft.trim();
                      if (!text) return;
                      onAddItem(group.topic, text);
                      setDraftByTopic((prev) => ({ ...prev, [group.topic]: "" }));
                    }}
                    returnKeyType="done"
                    maxLength={500}
                  />
                  <Pressable
                    style={[s.inlineAddBtn, !draft.trim() && s.inlineAddBtnDisabled]}
                    disabled={!draft.trim()}
                    onPress={() => {
                      const text = draft.trim();
                      if (!text) return;
                      onAddItem(group.topic, text);
                      setDraftByTopic((prev) => ({ ...prev, [group.topic]: "" }));
                    }}
                  >
                    <Ionicons
                      name="add"
                      size={20}
                      color={draft.trim() ? C.primary : C.textTertiary}
                    />
                  </Pressable>
                </View>

                {group.done.length > 0 ? (
                  <View style={s.doneBlock}>
                    <Text style={s.doneLabel}>
                      {t("todos.done")} ({group.done.length})
                    </Text>
                    {group.done.map((todo) => (
                      <ListItemRow
                        key={todo.id}
                        todo={todo}
                        busy={togglingId === todo.id}
                        onToggle={() => onToggle(todo)}
                        onDelete={() => onDelete(todo)}
                      />
                    ))}
                  </View>
                ) : null}
              </>
            ) : null}
          </View>
        </ScaleDecorator>
      );
    },
    [
      C,
      collapsed,
      draftByTopic,
      onAddItem,
      onDelete,
      onDeleteGroup,
      onReorderItems,
      onToggle,
      s,
      togglingId,
      toggleCollapsed,
      t,
    ],
  );

  const listData = useMemo(() => groups, [groups]);

  if (listData.length === 0) {
    return null;
  }

  return (
    <DraggableFlatList
      data={listData}
      keyExtractor={(group) => group.topic}
      scrollEnabled={false}
      onDragEnd={({ data }) => onReorderGroups(data.map((group) => group.topic))}
      renderItem={renderGroup}
      contentContainerStyle={s.container}
    />
  );
}

function ListItemRow({
  todo,
  busy,
  dragging,
  onDrag,
  onToggle,
  onDelete,
}: {
  todo: Todo;
  busy?: boolean;
  dragging?: boolean;
  onDrag?: () => void;
  onToggle: () => void;
  onDelete: () => void;
}) {
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  return (
    <View style={[s.itemRow, dragging && s.itemDragging]}>
      {onDrag ? (
        <Pressable onPressIn={onDrag} hitSlop={8} style={s.dragHandle}>
          <Ionicons name="reorder-three" size={20} color={C.textTertiary} />
        </Pressable>
      ) : (
        <View style={s.dragSpacer} />
      )}
      <Pressable
        onPress={onToggle}
        hitSlop={10}
        disabled={busy}
        accessibilityRole="checkbox"
        accessibilityState={{ checked: todo.checked, disabled: busy }}
      >
        <Ionicons
          name={todo.checked ? "checkbox" : "square-outline"}
          size={22}
          color={todo.checked ? C.primary : C.textTertiary}
        />
      </Pressable>
      <Text
        style={[s.itemText, todo.checked && s.itemDone]}
        numberOfLines={4}
        selectable
      >
        {todo.content}
      </Text>
      <Pressable onPress={onDelete} hitSlop={8}>
        <Ionicons name="trash-outline" size={16} color={C.textTertiary} />
      </Pressable>
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
  container: { paddingBottom: 8 },
  group: {
    marginHorizontal: 12,
    marginBottom: 12,
    borderRadius: 14,
    backgroundColor: C.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.border,
    overflow: "hidden",
  },
  groupDragging: { opacity: 0.92 },
  groupHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.border,
  },
  groupHeaderMain: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  groupTitle: { flex: 1, fontSize: 16, fontWeight: "700", color: C.text },
  groupCount: { fontSize: 12, color: C.textSecondary, marginRight: 4 },
  groupHint: {
    fontSize: 13,
    color: C.textTertiary,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  dragHandle: { padding: 4 },
  itemRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 10,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.border,
  },
  itemDragging: { backgroundColor: C.primaryLight },
  dragSpacer: { width: 28 },
  itemText: { flex: 1, fontSize: 16, lineHeight: 22, color: C.text },
  itemDone: { color: C.textTertiary, textDecorationLine: "line-through" },
  inlineAddRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 10,
    paddingVertical: 10,
  },
  inlineInput: {
    flex: 1,
    fontSize: 15,
    color: C.text,
    backgroundColor: C.bg,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: C.border,
  },
  inlineAddBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: C.bg,
  },
  inlineAddBtnDisabled: { opacity: 0.45 },
  doneBlock: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: C.border,
    paddingTop: 4,
  },
  doneLabel: {
    fontSize: 12,
    fontWeight: "600",
    color: C.textSecondary,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  });
}
