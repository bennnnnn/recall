import { useEffect, useMemo, useState } from "react";
import { Text, TextInput, View } from "react-native";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { SheetFormHeader } from "@/components/SheetFormHeader";
import { makeTodosStyles } from "@/features/todos/components/todosStyles";
import { TodoDateFields } from "@/features/todos/components/TodoDateFields";
import type { RecurrenceRule, Todo } from "@/lib/api";
import { useTheme } from "@/lib/theme";

function dueFromTodo(todo: Todo): Date | null {
  if (!todo.due_at) return null;
  const due = new Date(todo.due_at);
  return Number.isFinite(due.getTime()) ? due : null;
}

export function TodoEditorSheet({
  visible,
  saving,
  todos,
  editTodo,
  onClose,
  onSave,
}: {
  visible: boolean;
  saving: boolean;
  todos: Todo[];
  /** When set, the sheet edits that to-do, including its optional date. */
  editTodo?: Todo | null;
  onClose: () => void;
  onSave: (content: string, dueDate: Date | null, recurrence: RecurrenceRule | null) => void;
}) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const [text, setText] = useState("");
  const [dueDate, setDueDate] = useState<Date | null>(null);
  const [repeat, setRepeat] = useState<RecurrenceRule | null>(null);

  useEffect(() => {
    if (!visible) return;
    setText(editTodo?.content ?? "");
    setDueDate(editTodo ? dueFromTodo(editTodo) : null);
    setRepeat(editTodo?.recurrence_rule ?? null);
  }, [visible, editTodo]);

  const canSave = text.trim().length > 0 && !saving;

  const handleClose = () => {
    if (saving) return;
    onClose();
  };

  const handleSave = () => {
    if (!canSave) return;
    onSave(text, dueDate, repeat);
  };

  return (
    <AppSheet
      visible={visible}
      onClose={handleClose}
      variant="bottom"
      keyboardAvoiding
      withHandle={false}
      contentContainerStyle={[s.sheet, { paddingHorizontal: 0, paddingTop: 0 }]}
    >
      <SheetFormHeader
        title={editTodo ? t("todos.edit_todo") : t("todos.new_todo")}
        onCancel={handleClose}
        onSave={handleSave}
        cancelLabel={t("common.cancel")}
        saveLabel={t("todos.save")}
        saving={saving}
        saveDisabled={text.trim().length === 0}
      />

      <View style={s.sheetBody}>
        <Text style={s.formLabel}>{t("todos.todo_label")}</Text>
        <TextInput
          style={s.titleInput}
          placeholder={t("todos.todo_placeholder")}
          placeholderTextColor={C.textDisabled}
          value={text}
          onChangeText={setText}
          autoFocus={!editTodo}
          returnKeyType="done"
          maxLength={500}
          editable={!saving}
        />

        <TodoDateFields
          key={editTodo?.id ?? "new"}
          dueDate={dueDate}
          onDueDateChange={setDueDate}
          repeat={repeat}
          onRepeatChange={setRepeat}
          todos={todos}
          excludeId={editTodo?.id}
          disabled={saving}
        />
      </View>
    </AppSheet>
  );
}
