import { useEffect, useMemo, useState } from "react";
import { Text, TextInput, View } from "react-native";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { SheetFormHeader } from "@/components/SheetFormHeader";
import { ReminderScheduleFields } from "@/components/todos/ReminderScheduleFields";
import { defaultDueDate } from "@/components/todos/todoHelpers";
import { makeTodosStyles } from "@/components/todos/todosStyles";
import type { RecurrenceRule, Todo } from "@/lib/api";
import { useTheme } from "@/lib/theme";

function dueFromTodo(todo: Todo): Date {
  const due = todo.due_at ? new Date(todo.due_at) : defaultDueDate();
  return Number.isFinite(due.getTime()) ? due : defaultDueDate();
}

export function AddReminderSheet({
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
  /** When set, the sheet edits that reminder (content + due + repeat). */
  editTodo?: Todo | null;
  onClose: () => void;
  onSave: (content: string, dueDate: Date, recurrence: RecurrenceRule | null) => void;
}) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const [text, setText] = useState("");
  const [dueDate, setDueDate] = useState(() => defaultDueDate());
  const [repeat, setRepeat] = useState<RecurrenceRule | null>(null);

  useEffect(() => {
    if (!visible) return;
    setText(editTodo?.content ?? "");
    setDueDate(editTodo ? dueFromTodo(editTodo) : defaultDueDate());
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
        title={editTodo ? t("todos.edit_reminder") : t("todos.reminder_sheet_title")}
        onCancel={handleClose}
        onSave={handleSave}
        cancelLabel={t("common.cancel")}
        saveLabel={t("todos.save")}
        saving={saving}
        saveDisabled={text.trim().length === 0}
      />

      <View style={s.sheetBody}>
        <Text style={s.formLabel}>{t("todos.reminder_label")}</Text>
        <TextInput
          style={s.titleInput}
          placeholder={t("todos.reminder_placeholder")}
          placeholderTextColor={C.textDisabled}
          value={text}
          onChangeText={setText}
          autoFocus={!editTodo}
          returnKeyType="done"
          maxLength={500}
          editable={!saving}
        />

        <ReminderScheduleFields
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
