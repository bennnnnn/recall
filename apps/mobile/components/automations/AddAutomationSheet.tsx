import { useEffect, useMemo, useState } from "react";
import { Keyboard, Platform, Pressable, Text, TextInput, View } from "react-native";
import type { DateTimePickerEvent } from "@react-native-community/datetimepicker";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import {
  AutomationFrequencyPicker,
  automationFrequencyMessageKey,
} from "@/components/automations/AutomationFrequencyPicker";
import { makeAutomationsStyles } from "@/components/automations/automationsStyles";
import { Icon } from "@/components/Icon";
import { SheetFormHeader } from "@/components/SheetFormHeader";
import { ReminderDateTimePicker } from "@/components/todos/ReminderDateTimePicker";
import { defaultDueDate } from "@/components/todos/todoHelpers";
import type { AutomationFrequency } from "@/lib/api";
import { describeDueAt, toDueAtIso } from "@/lib/todos/dueDate";
import { useTheme } from "@/lib/theme";

type Initial = {
  title: string | null;
  prompt: string;
  frequency: AutomationFrequency;
  nextRunAt: Date;
} | null;

export function AddAutomationSheet({
  visible,
  saving,
  initial,
  onClose,
  onSave,
}: {
  visible: boolean;
  saving: boolean;
  /** null = create; a value = edit that automation's fields. */
  initial: Initial;
  onClose: () => void;
  onSave: (title: string | null, prompt: string, frequency: AutomationFrequency, nextRunAt: Date) => void;
}) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeAutomationsStyles(C), [C]);
  const isEdit = initial != null;
  const [title, setTitle] = useState(initial?.title ?? "");
  const [text, setText] = useState(initial?.prompt ?? "");
  const [nextRunAt, setNextRunAt] = useState(() => initial?.nextRunAt ?? defaultDueDate());
  const [frequency, setFrequency] = useState<AutomationFrequency>(initial?.frequency ?? "daily");
  const [showPicker, setShowPicker] = useState(Platform.OS === "ios");
  const [frequencyPickerOpen, setFrequencyPickerOpen] = useState(false);

  useEffect(() => {
    if (!visible) return;
    setTitle(initial?.title ?? "");
    setText(initial?.prompt ?? "");
    setNextRunAt(initial?.nextRunAt ?? defaultDueDate());
    setFrequency(initial?.frequency ?? "daily");
    setShowPicker(Platform.OS === "ios");
    setFrequencyPickerOpen(false);
    // Only reset when the sheet opens (or the automation being edited changes).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, initial?.title, initial?.prompt, initial?.frequency, initial?.nextRunAt?.getTime()]);

  const canSave = text.trim().length > 0 && !saving;

  const handleClose = () => {
    if (saving) return;
    onClose();
  };

  const onPickerChange = (event: DateTimePickerEvent, date?: Date) => {
    if (Platform.OS === "android") {
      setShowPicker(false);
      if (event.type === "dismissed" || !date) return;
      setNextRunAt(date);
      return;
    }
    if (date) setNextRunAt(date);
  };

  const handleSave = () => {
    if (!canSave) return;
    onSave(title.trim() || null, text, frequency, nextRunAt);
  };

  const frequencyLabel = t(automationFrequencyMessageKey(frequency));

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
        title={t(isEdit ? "automations.sheet_title_edit" : "automations.sheet_title_create")}
        onCancel={handleClose}
        onSave={handleSave}
        cancelLabel={t("common.cancel")}
        saveLabel={t("common.save")}
        saving={saving}
        saveDisabled={text.trim().length === 0}
      />

      <View style={s.sheetBody}>
        <Text style={s.formLabel}>{t("automations.title_label")}</Text>
        <TextInput
          style={s.titleInput}
          placeholder={t("automations.title_placeholder")}
          placeholderTextColor={C.textDisabled}
          value={title}
          onChangeText={setTitle}
          autoFocus={!isEdit}
          maxLength={200}
          editable={!saving}
        />

        <Text style={[s.formLabel, s.fieldGap]}>{t("automations.prompt_label")}</Text>
        <TextInput
          style={s.promptInput}
          placeholder={t("automations.prompt_placeholder")}
          placeholderTextColor={C.textDisabled}
          value={text}
          onChangeText={setText}
          multiline
          maxLength={2000}
          editable={!saving}
        />

        <Text style={[s.formLabel, s.fieldGap]}>{t("automations.next_run_label")}</Text>
        {Platform.OS === "ios" && showPicker ? (
          <ReminderDateTimePicker value={nextRunAt} onChange={onPickerChange} disabled={saving} />
        ) : (
          <Pressable
            style={s.dateChip}
            onPress={() => {
              Keyboard.dismiss();
              setShowPicker(true);
            }}
            disabled={saving}
            accessibilityRole="button"
            accessibilityLabel={t("automations.next_run_label")}
          >
            <Icon name="calendar" size={18} color={C.primary} />
            <Text style={s.dateChipText}>
              {describeDueAt(toDueAtIso(nextRunAt))?.label ?? ""}
            </Text>
          </Pressable>
        )}
        {Platform.OS === "android" && showPicker ? (
          <ReminderDateTimePicker value={nextRunAt} onChange={onPickerChange} disabled={saving} />
        ) : null}

        <Text style={[s.formLabel, s.fieldGap]}>{t("automations.frequency_label")}</Text>
        <View>
          <Pressable
            style={[s.frequencyField, frequencyPickerOpen && s.frequencyFieldOpen]}
            onPress={() => {
              Keyboard.dismiss();
              setFrequencyPickerOpen((open) => !open);
            }}
            disabled={saving}
            accessibilityRole="button"
            accessibilityState={{ expanded: frequencyPickerOpen }}
            accessibilityLabel={`${t("automations.frequency_label")}, ${frequencyLabel}`}
          >
            <Text style={s.frequencyFieldText}>{frequencyLabel}</Text>
            <Icon
              name={frequencyPickerOpen ? "chevron-up" : "chevron-down"}
              size={18}
              color={C.textTertiary}
            />
          </Pressable>
          {frequencyPickerOpen ? (
            <AutomationFrequencyPicker
              selected={frequency}
              onSelect={(next) => {
                setFrequency(next);
                setFrequencyPickerOpen(false);
              }}
            />
          ) : null}
        </View>
      </View>
    </AppSheet>
  );
}
