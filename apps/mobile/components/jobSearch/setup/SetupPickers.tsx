import { Platform, Pressable, Text } from "react-native";
import type { DateTimePickerEvent } from "@react-native-community/datetimepicker";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { SettingsPickerSheet } from "@/components/settings/SettingsPickerSheet";
import { ReminderDateTimePicker } from "@/components/todos/ReminderDateTimePicker";
import type {
  JobSearchExperience,
  JobSearchFrequency,
} from "@/lib/api";

import {
  EXPERIENCE_VALUES,
  FREQUENCY_VALUES,
  useSetupStyles,
} from "./setupShared";

type ResultCount = 5 | 10 | 15;

type Props = {
  isPro: boolean;
  busy: boolean;
  showExperience: boolean;
  showCount: boolean;
  showFrequency: boolean;
  showPicker: boolean;
  level: JobSearchExperience;
  count: ResultCount;
  frequency: JobSearchFrequency;
  nextRunAt: Date;
  experienceLabel: (value: JobSearchExperience) => string;
  frequencyLabel: (value: JobSearchFrequency) => string;
  onCloseExperience: () => void;
  onCloseCount: () => void;
  onCloseFrequency: () => void;
  onClosePicker: () => void;
  onSelectExperience: (value: JobSearchExperience) => void;
  onSelectCount: (value: ResultCount) => void;
  onSelectFrequency: (value: JobSearchFrequency) => void;
  onPickerChange: (event: DateTimePickerEvent, date?: Date) => void;
};

export function SetupPickers({
  isPro,
  busy,
  showExperience,
  showCount,
  showFrequency,
  showPicker,
  level,
  count,
  frequency,
  nextRunAt,
  experienceLabel,
  frequencyLabel,
  onCloseExperience,
  onCloseCount,
  onCloseFrequency,
  onClosePicker,
  onSelectExperience,
  onSelectCount,
  onSelectFrequency,
  onPickerChange,
}: Props) {
  const { t } = useTranslation();
  const s = useSetupStyles();

  return (
    <>
      <SettingsPickerSheet
        visible={showExperience}
        options={EXPERIENCE_VALUES.map((value) => ({
          key: value,
          label: experienceLabel(value),
        }))}
        selectedKey={level}
        onClose={onCloseExperience}
        onSelect={(key) => onSelectExperience(key as JobSearchExperience)}
      />
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
