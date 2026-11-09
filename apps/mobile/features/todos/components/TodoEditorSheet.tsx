import { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useState } from "react";
import { BackHandler, ScrollView, Text, TextInput, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Sheet } from "@/ui/overlay/Sheet";
import { SheetFormHeader } from "@/ui/overlay/SheetFormHeader";
import { TodoCategoryField } from "@/features/todos/components/TodoCategoryField";
import { makeTodosStyles } from "@/features/todos/components/todosStyles";
import { TodoDateFields } from "@/features/todos/components/TodoDateFields";
import { TodoPickers, type TodoPicker } from "@/features/todos/components/TodoPickers";
import { useRemindAt } from "@/features/todos/hooks/useRemindAt";
import { dueOfTodo, sameDue, type TodoDue } from "@/features/todos/model/dueDate";
import { DEFAULT_TOPIC } from "@/features/todos/model/todoTopics";
import type { RecurrenceRule, Todo } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import { TextField } from "@/ui/controls/TextField";

type TodoEditorDraft = {
  content: string;
  /** The date, and its time when it has one. */
  due: TodoDue | null;
  recurrence: RecurrenceRule | null;
  topic: string;
};

export type TodoEditorHandle = {
  leave: () => void;
  /** Unsaved detail edits. Null when the form matches the saved to-do. */
  pending: () => TodoEditorDraft | null;
};

export const TodoEditorSheet = forwardRef<
  TodoEditorHandle,
  {
    visible: boolean;
    saving: boolean;
    todos: Todo[];
    /** Full page under the navigation header, instead of a bottom sheet. */
    page?: boolean;
    /** The profile's reminder lead, which Remind at on the detail page sets. */
    leadMinutes?: number;
    onChangeLead?: (minutes: number) => Promise<void>;
    /** When set, the form edits that to-do, including its optional date. */
    editTodo?: Todo | null;
    /** `editTodo` as the list holds it now: its notify_at moves with the lead time,
     * quiet hours and zone while the page is open. */
    savedTodo?: Todo | null;
    /** Completed to-dos can be viewed, unmarked, or deleted. Fields stay fixed. */
    readOnly?: boolean;
    onClose: () => void;
    onSave: (
      content: string,
      due: TodoDue | null,
      recurrence: RecurrenceRule | null,
      topic: string,
    ) => void;
  }
>(function TodoEditorSheet({
  visible,
  saving,
  todos,
  page = false,
  leadMinutes,
  onChangeLead,
  editTodo,
  savedTodo,
  readOnly = false,
  onClose,
  onSave,
}, ref) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const [text, setText] = useState("");
  const [due, setDue] = useState<TodoDue | null>(null);
  const [repeat, setRepeat] = useState<RecurrenceRule | null>(null);
  const [topic, setTopic] = useState(DEFAULT_TOPIC);
  const [picker, setPicker] = useState<TodoPicker | null>(null);

  useEffect(() => {
    if (!visible) {
      setPicker(null);
      return;
    }
    setText(editTodo?.content ?? "");
    setDue(editTodo ? dueOfTodo(editTodo) : null);
    setRepeat(editTodo?.recurrence_rule ?? null);
    setTopic(editTodo?.topic?.trim() || DEFAULT_TOPIC);
    setPicker(null);
  }, [visible, editTodo]);

  const canSave = text.trim().length > 0 && !saving;
  // Remind at on the detail page: the server's instant for the time and repeat on screen; a
  // date alone has none.
  const remindAt = useRemindAt({ dueDate: due?.hasTime ? due.date : null, repeat, saved: savedTodo ?? editTodo, enabled: page && visible });

  const closePicker = () => setPicker(null);

  const handleClose = () => {
    if (saving) return;
    if (picker) {
      closePicker();
      return;
    }
    onClose();
  };

  const handleSave = () => {
    if (!canSave) return;
    onSave(text, due, repeat, topic);
  };

  const dirty =
    text !== (editTodo?.content ?? "") ||
    !sameDue(due, editTodo ? dueOfTodo(editTodo) : null) ||
    repeat !== (editTodo?.recurrence_rule ?? null) ||
    topic !== (editTodo?.topic?.trim() || DEFAULT_TOPIC);

  const leave = useCallback(() => {
    if (saving) return;
    if (picker) {
      setPicker(null);
      return;
    }
    if (readOnly || !dirty || text.trim().length === 0) {
      onClose();
      return;
    }
    onSave(text, due, repeat, topic);
  }, [saving, picker, readOnly, dirty, text, due, repeat, topic, onClose, onSave]);

  const pending = useCallback((): TodoEditorDraft | null => {
    if (readOnly || !dirty || text.trim().length === 0) return null;
    return { content: text, due, recurrence: repeat, topic };
  }, [readOnly, dirty, text, due, repeat, topic]);

  useImperativeHandle(ref, () => ({ leave, pending }), [leave, pending]);

  useEffect(() => {
    if (!visible) return;
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      if (page) {
        leave();
        return true;
      }
      if (picker) {
        setPicker(null);
        return true;
      }
      onClose();
      return true;
    });
    return () => sub.remove();
  }, [visible, page, picker, leave, onClose]);

  const fields = page ? (
    <>
      <TodoCategoryField
        review
        topic={topic}
        disabled={saving || readOnly}
        onOpen={() => setPicker("category")}
      />
      {readOnly ? (
        <Text style={s.reviewTitle}>{text}</Text>
      ) : (
        <TextInput
          style={s.reviewTitle}
          placeholder={t("todos.todo_placeholder")}
          placeholderTextColor={C.textTertiary}
          value={text}
          onChangeText={setText}
          autoFocus={!editTodo}
          returnKeyType="done"
          multiline
          scrollEnabled={false}
          maxLength={500}
          editable={!saving}
          underlineColorAndroid="transparent"
        />
      )}
      <TodoDateFields
        key={editTodo?.id ?? "new"}
        review
        due={due}
        onDueChange={setDue}
        repeat={repeat}
        onRepeatChange={setRepeat}
        todos={todos}
        excludeId={editTodo?.id}
        remindAt={remindAt}
        disabled={saving || readOnly}
        leadMinutes={leadMinutes}
        onChangeLead={readOnly ? undefined : onChangeLead}
        onOpen={setPicker}
      />
    </>
  ) : (
    <>
      <Text style={s.formLabel}>{t("todos.todo_label")}</Text>
      <TextField
        placeholder={t("todos.todo_placeholder")}
        value={text}
        onChangeText={setText}
        autoFocus={!editTodo}
        returnKeyType="done"
        maxLength={500}
        editable={!saving}
        accessibilityLabel={t("todos.todo_label")}
      />

      <TodoCategoryField
        topic={topic}
        disabled={saving}
        onOpen={() => setPicker("category")}
      />

      <TodoDateFields
        key={editTodo?.id ?? "new"}
        due={due}
        onDueChange={setDue}
        repeat={repeat}
        onRepeatChange={setRepeat}
        todos={todos}
        excludeId={editTodo?.id}
        disabled={saving}
        onOpen={setPicker}
      />
    </>
  );

  if (page) {
    if (!visible) return null;
    return (
      <View style={s.detailPage}>
        <ScrollView
          style={s.detailPage}
          contentContainerStyle={s.sheetBody}
          keyboardShouldPersistTaps="handled"
        >
          {fields}
        </ScrollView>
        <TodoPickers
          picker={readOnly ? null : picker}
          topic={topic}
          todos={todos}
          due={due}
          repeat={repeat}
          disabled={saving}
          onTopic={setTopic}
          onDue={setDue}
          onRepeat={setRepeat}
          onClose={closePicker}
        />
      </View>
    );
  }

  return (
    <>
    <Sheet
      embedded
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

      <View style={s.sheetBody}>{fields}</View>
    </Sheet>
    <TodoPickers
      picker={visible ? picker : null}
      topic={topic}
      todos={todos}
      due={due}
      repeat={repeat}
      disabled={saving}
      onTopic={setTopic}
      onDue={setDue}
      onRepeat={setRepeat}
      onClose={closePicker}
    />
    </>
  );
});
