import { Platform, Pressable, Text } from "react-native";
import type { DateTimePickerEvent } from "@react-native-community/datetimepicker";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { SettingsPickerSheet } from "@/components/settings/SettingsPickerSheet";
import { ReminderDateTimePicker } from "@/features/todos/components/ReminderDateTimePicker";
import type { JobSearchFrequency } from "@/lib/api";

import { FREQUENCY_VALUES, useSetupStyles } from "./setupShared";

type ResultCount = 5 | 10 | 15;

type Props = {
  isPro: boolean;
  busy: boolean;
  showCount: boolean;
  showFrequency: boolean;
  showPicker: boolean;
  count: ResultCount;
  frequency: JobSearchFrequency;
  nextRunAt: Date;
  frequencyLabel: (value: JobSearchFrequency) => string;
  onCloseCount: () => void;
  onCloseFrequency: () => void;
  onClosePicker: () => void;
  onSelectCount: (value: ResultCount) => void;
  onSelectFrequency: (value: JobSearchFrequency) => void;
  onPickerChange: (event: DateTimePickerEvent, date?: Date) => void;
};

export function SetupPickers({
  isPro,
  busy,
  showCount,
  showFrequency,
  showPicker,
  count,
  frequency,
  nextRunAt,
  frequencyLabel,
  onCloseCount,
  onCloseFrequency,
  onClosePicker,
  onSelectCount,
  onSelectFrequency,
  onPickerChange,
}: Props) {
  const { t } = useTranslation();
  const s = useSetupStyles();

  return (
    <>
      <SettingsPickerSheet
        visible={showCount}
        options={([5, 10, 15] as const).map((option) => ({
          key: String(option),
          label: `${option} ${t("my_job.count_jobs")}`,
          disabled: !isPro && option !== 5,
          note: !isPro && option !== 5 ? t("my_job.count_pro") : undefined,
        }))}
        selectedKey={String(count)}
        onClose={onCloseCount}
        onSelect={(key) => onSelectCount(Number(key) as ResultCount)}
      />
      <SettingsPickerSheet
        visible={showFrequency}
        options={FREQUENCY_VALUES.map((value) => ({
          key: value,
          label: frequencyLabel(value),
          disabled: !isPro && value !== "weekly",
          note:
            !isPro && value !== "weekly" ? t("my_job.count_pro") : undefined,
        }))}
        selectedKey={frequency}
        onClose={onCloseFrequency}
        onSelect={(key) => onSelectFrequency(key as JobSearchFrequency)}
      />

      {/* Android fires native date→time dialogs from the rendered picker itself;
          iOS gets the spinner inside a floating sheet with a Done button. */}
      {Platform.OS === "android" && showPicker ? (
        <ReminderDateTimePicker
          mode="datetime"
          value={nextRunAt}
          onChange={onPickerChange}
          disabled={busy}
        />
      ) : null}
      <AppSheet
        visible={Platform.OS === "ios" && showPicker}
        onClose={onClosePicker}
        withHandle
      >
        <Text style={s.pickerTitle}>{t("my_job.first_delivery_label")}</Text>
        <ReminderDateTimePicker
          mode="datetime"
          value={nextRunAt}
          onChange={onPickerChange}
          disabled={busy}
        />
        <Pressable
          style={({ pressed }) => [s.pickerDone, pressed && s.pressed]}
          onPress={onClosePicker}
          accessibilityRole="button"
        >
          <Text style={s.pickerDoneText}>{t("common.done")}</Text>
        </Pressable>
      </AppSheet>
    </>
  );
}
