import type { RefObject } from "react";
import type { View } from "react-native";
import { useTranslation } from "react-i18next";

import { SelectMenu } from "@/ui/overlay/SelectMenu";
import { DateTimePickerDialog } from "@/ui/pickers/DateTimePickerDialog";
import type { JobSearchFrequency } from "@/lib/api";

import { FREQUENCY_VALUES } from "./setupShared";

type ResultCount = 5 | 10 | 15;

type Props = {
  countRowRef: RefObject<View | null>;
  frequencyRowRef: RefObject<View | null>;
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
  onPickNextRun: (date: Date) => void;
};

export function SetupPickers({
  countRowRef,
  frequencyRowRef,
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
  onPickNextRun,
}: Props) {
  const { t } = useTranslation();

  return (
    <>
      <SelectMenu
        visible={showCount}
        anchorRef={countRowRef}
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
      <SelectMenu
        visible={showFrequency}
        anchorRef={frequencyRowRef}
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

      <DateTimePickerDialog
        visible={showPicker}
        value={nextRunAt}
        minimumDate={new Date()}
        onConfirm={(date) => {
          if (!busy) onPickNextRun(date);
          onClosePicker();
        }}
        onCancel={onClosePicker}
      />
    </>
  );
}
