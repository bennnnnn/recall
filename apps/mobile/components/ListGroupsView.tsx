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
import Swipeable from "react-native-gesture-handler/ReanimatedSwipeable";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { Radius } from "@/lib/radius";
import type { Todo } from "@/lib/api";
import type { ListGroup } from "@/lib/listGroups";
import { Theme, useTheme } from "@/lib/theme";

const CHECKBOX_SIZE = 22;

type Props = {
  groups: ListGroup[];
  initialExpandedTopic?: string;
  togglingId: string | null;
  projectTitleById?: Map<string, string>;
  onReorderGroups: (topics: string[]) => void;
  onReorderItems: (topic: string, ordered: Todo[]) => void;
  onToggle: (todo: Todo) => void;
  onAddItem: (topic: string, text: string) => void;
  onDeleteItem: (todo: Todo) => void;
  onLinkProject?: (todo: Todo) => void;
  onDeleteList: (topic: string) => void;
};

export function ListGroupsView({
  groups,
  initialExpandedTopic,
  togglingId,
  projectTitleById,
  onReorderGroups,
  onReorderItems,
  onToggle,
  onAddItem,
  onDeleteItem,
  onLinkProject,
  onDeleteList,
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

  const listData = useMemo(() => groups, [groups]);

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

      const isDefault = group.isDefault;
      const openCount = group.open.length;
      const showHeader = !isDefault;
      const expanded = isDefault || !isCollapsed;

      return (
        <ScaleDecorator>
          <View style={s.groupWrap}>
            {showHeader ? (
              <View style={s.sectionRow}>
                <Pressable
                  style={s.sectionMain}
                  onPress={() => toggleCollapsed(group.topic)}
                  onLongPress={drag}
                  delayLongPress={280}
                >
                  <Text style={s.sectionTitle} numberOfLines={1}>
                    {group.title}
                  </Text>
                  <Text style={s.sectionCount}>{openCount}</Text>
                </Pressable>
                {openCount === 0 ? (
                  <Pressable
                    hitSlop={8}
                    onPress={() => onDeleteList(group.topic)}
                    accessibilityRole="button"
                    accessibilityLabel={t("lists.delete_group_confirm")}
                  >
                    <Ionicons name="trash-outline" size={16} color={C.textTertiary} />
                  </Pressable>
                ) : null}
                <Pressable hitSlop={8} onPress={() => toggleCollapsed(group.topic)}>
                  <Ionicons
                    name={isCollapsed ? "chevron-down" : "chevron-up"}
                    size={18}
                    color={C.textTertiary}
                  />
                </Pressable>
              </View>
            ) : null}

            {expanded ? (
              <View style={[s.groupBody, isActive && s.groupBodyDragging]}>
                {group.open.length > 0 ? (
                  <DraggableFlatList
                    data={group.open}
                    keyExtractor={(todo) => todo.id}
                    scrollEnabled={false}
                    onDragEnd={({ data }) => onReorderItems(group.topic, data)}
                    renderItem={({ item: todo, drag: dragItem, isActive: itemActive }) => (
                      <ScaleDecorator>
                        <ListItemRow
                          todo={todo}
                          variant="open"
                          busy={togglingId === todo.id}
                          dragging={itemActive}
                          onDrag={dragItem}
                          projectTitle={
                            todo.project_id && projectTitleById
                              ? projectTitleById.get(todo.project_id) ?? null
                              : null
                          }
                          onToggle={() => onToggle(todo)}
                          onLinkProject={
                            onLinkProject ? () => onLinkProject(todo) : undefined
                          }
                          onDelete={() => onDeleteItem(todo)}
                        />
                      </ScaleDecorator>
                    )}
                  />
                ) : null}

                <View style={s.addSection}>
                  <View style={s.addInputWrap}>
                    <TextInput
                      style={s.addInput}
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
                  </View>
                  <Button
                    title={t("common.add")}
                    onPress={() => {
                      const text = draft.trim();
                      if (!text) return;
                      onAddItem(group.topic, text);
                      setDraftByTopic((prev) => ({ ...prev, [group.topic]: "" }));
                    }}
                    disabled={!draft.trim()}
                    style={s.addButton}
                  />
                </View>

                {group.done.length > 0 ? (
                  <View style={s.doneSection}>
                    <Text style={s.doneHeading}>
                      {t("todos.done")} ({group.done.length})
                    </Text>
                    {group.done.map((todo) => (
                      <ListItemRow
                        key={todo.id}
                        todo={todo}
                        variant="done"
                        busy={togglingId === todo.id}
                        projectTitle={
                          todo.project_id && projectTitleById
                            ? projectTitleById.get(todo.project_id) ?? null
                            : null
                        }
                        onToggle={() => onToggle(todo)}
                        onDelete={() => onDeleteItem(todo)}
                      />
                    ))}
                  </View>
                ) : null}
              </View>
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
      onDeleteItem,
      onDeleteList,
      onLinkProject,
      onReorderItems,
      onToggle,
      projectTitleById,
      s,
      togglingId,
      toggleCollapsed,
      t,
    ],
  );

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
  variant,
  busy,
  dragging,
  onDrag,
  projectTitle,
  onToggle,
  onLinkProject,
  onDelete,
}: {
  todo: Todo;
  variant: "open" | "done";
  busy?: boolean;
  dragging?: boolean;
  onDrag?: () => void;
  projectTitle?: string | null;
  onToggle: () => void;
  onLinkProject?: () => void;
  onDelete: () => void;
}) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);

  const row = (
    <Pressable
      onLongPress={onDrag}
      delayLongPress={220}
      disabled={!onDrag}
      style={[s.row, dragging && s.rowDragging]}
    >
      <Pressable
        onPress={onToggle}
        hitSlop={10}
        disabled={busy}
        style={s.checkbox}
        accessibilityRole="checkbox"
        accessibilityState={{ checked: todo.checked, disabled: busy }}
      >
        <Ionicons
          name={todo.checked ? "checkbox" : "square-outline"}
          size={CHECKBOX_SIZE}
          color={todo.checked ? C.primary : C.textTertiary}
        />
      </Pressable>
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={[s.rowText, todo.checked && s.rowDone]} numberOfLines={4} selectable>
          {todo.content}
        </Text>
        {projectTitle ? (
          <Text style={{ fontSize: 12, fontWeight: "500", color: C.textSecondary }} numberOfLines={1}>
            {t("todos.project_linked", { title: projectTitle })}
          </Text>
        ) : null}
      </View>
      {variant === "open" && onLinkProject ? (
        <Pressable
          onPress={onLinkProject}
          hitSlop={8}
          accessibilityLabel={t("todos.link_project")}
        >
          <Ionicons
            name={todo.project_id ? "folder" : "folder-outline"}
            size={16}
            color={todo.project_id ? C.primary : C.textTertiary}
          />
        </Pressable>
      ) : null}
      {variant === "done" ? (
        <Pressable
          onPress={onDelete}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel={t("common.delete")}
        >
          <Ionicons name="trash-outline" size={16} color={C.textTertiary} />
        </Pressable>
      ) : null}
    </Pressable>
  );

  if (variant !== "open") {
    return row;
  }

  return (
    <Swipeable
      friction={2}
      rightThreshold={40}
      enabled={!dragging}
      overshootRight={false}
      containerStyle={s.swipeContainer}
      renderRightActions={() => (
        <Pressable
          style={s.swipeDeleteAction}
          onPress={onDelete}
          accessibilityRole="button"
          accessibilityLabel={t("common.delete")}
        >
          <Ionicons name="trash-outline" size={18} color={C.onPrimary} />
          <Text style={s.swipeDeleteText}>{t("common.delete")}</Text>
        </Pressable>
      )}
    >
      {row}
    </Swipeable>
  );
}

function makeStyles(C: Theme) {
  const hairline = StyleSheet.hairlineWidth;
  return StyleSheet.create({
    container: {
      paddingBottom: 24,
      backgroundColor: C.bg,
    },
    groupWrap: {
      paddingHorizontal: 16,
      marginBottom: 24,
    },
    sectionRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: 8,
      paddingBottom: 8,
    },
    sectionMain: {
      flex: 1,
      flexDirection: "row",
      alignItems: "center",
      gap: 8,
      minWidth: 0,
    },
    // Named list titles are primary labels (same role as Learning card titles /
    // reminder body text) — not muted section captions.
    sectionTitle: {
      flex: 1,
      fontSize: 16,
      fontWeight: "700",
      color: C.text,
    },
    sectionCount: {
      fontSize: 13,
      fontWeight: "500",
      color: C.textSecondary,
      fontVariant: ["tabular-nums"],
    },
    groupBody: {
      backgroundColor: C.bg,
      overflow: "hidden",
    },
    groupBodyDragging: {
      backgroundColor: C.surface,
    },
    row: {
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      paddingHorizontal: 16,
      paddingVertical: 14,
      borderBottomWidth: hairline,
      borderBottomColor: C.border,
      backgroundColor: C.bg,
    },
    rowDragging: {
      backgroundColor: C.surface,
    },
    swipeContainer: {
      overflow: "hidden",
    },
    swipeDeleteAction: {
      width: 80,
      backgroundColor: C.danger,
      alignItems: "center",
      justifyContent: "center",
      gap: 2,
    },
    swipeDeleteText: {
      fontSize: 12,
      fontWeight: "600",
      color: C.onPrimary,
    },
    checkbox: {
      padding: 2,
    },
    rowText: {
      flex: 1,
      fontSize: 16,
      lineHeight: 22,
      color: C.text,
    },
    rowDone: {
      color: C.textTertiary,
      textDecorationLine: "line-through",
    },
    addSection: {
      flexDirection: "row",
      alignItems: "center",
      gap: 8,
      paddingHorizontal: 16,
      paddingVertical: 12,
      backgroundColor: C.bg,
      borderTopWidth: hairline,
      borderTopColor: C.border,
    },
    addInputWrap: {
      flex: 1,
      borderWidth: hairline,
      borderColor: C.border,
      borderRadius: Radius.sm,
      paddingHorizontal: 12,
      paddingVertical: 8,
      backgroundColor: C.bg,
    },
    addInput: {
      fontSize: 16,
      lineHeight: 22,
      color: C.text,
      paddingVertical: 0,
    },
    addButton: {
      minHeight: 40,
      paddingHorizontal: 16,
      paddingVertical: 8,
    },
    doneSection: {
      borderTopWidth: hairline,
      borderTopColor: C.border,
    },
    doneHeading: {
      fontSize: 12,
      fontWeight: "700",
      color: C.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
      paddingHorizontal: 16,
      paddingTop: 12,
      paddingBottom: 4,
    },
  });
}
