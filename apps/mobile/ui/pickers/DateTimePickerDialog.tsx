import { useEffect, useState } from "react";

import { timeFromDate, withTimeOfDay } from "@/lib/datetime/clockDial";

import { DatePickerDialog } from "./DatePickerDialog";
import { TimePickerDialog } from "./TimePickerDialog";

type Props = {
  visible: boolean;
  value: Date;
  onConfirm: (date: Date) => void;
  /** Cancel on either step. */
  onCancel: () => void;
  minimumDate?: Date | null;
  maximumDate?: Date | null;
  /** Force a 12- or 24-hour clock. Defaults to the device's. */
  is24Hour?: boolean;
  testID?: string;
};

/** A day, then a time: the date picker's OK opens the clock for the same value. */
export function DateTimePickerDialog({
  visible,
  value,
  onConfirm,
  onCancel,
  minimumDate,
  maximumDate,
  is24Hour,
  testID = "date-time-picker",
}: Props) {
  const [step, setStep] = useState<"date" | "time">("date");
  const [day, setDay] = useState(value);

  useEffect(() => {
    if (!visible) return;
    setStep("date");
    setDay(value);
    // Start from the caller's value each time the picker opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);

  return (
    <>
      <DatePickerDialog
        visible={visible && step === "date"}
        value={value}
        minimumDate={minimumDate}
        maximumDate={maximumDate}
        onConfirm={(date) => {
          setDay(date);
          setStep("time");
        }}
        onCancel={onCancel}
        testID={`${testID}-date`}
      />
      <TimePickerDialog
        visible={visible && step === "time"}
        value={timeFromDate(day)}
        is24Hour={is24Hour}
        onConfirm={(time) => onConfirm(withTimeOfDay(day, time))}
        onCancel={onCancel}
        testID={`${testID}-time`}
      />
    </>
  );
}
