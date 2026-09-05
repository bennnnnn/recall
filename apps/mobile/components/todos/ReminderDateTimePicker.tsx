import { useLayoutEffect, useRef, useState } from "react";
import { Platform } from "react-native";
import DateTimePicker, { type DateTimePickerEvent } from "@react-native-community/datetimepicker";

type Props = {
  value: Date;
  disabled?: boolean;
  onChange: (event: DateTimePickerEvent, date?: Date) => void;
};

/** Android exposes separate dialogs; only a completed date and time is saved. */
export function ReminderDateTimePicker({ value, disabled, onChange }: Props) {
  const [step, setStep] = useState<"date" | "time">("date");
  const activeStep = useRef<"date" | "time" | null>("date");
  const selectedDate = useRef(value);
  const mounted = useRef(false);
  const disabledRef = useRef(disabled);
  disabledRef.current = disabled;
  useLayoutEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const handleChange = (event: DateTimePickerEvent, date?: Date) => {
    if (!mounted.current || disabledRef.current) return;
    if (Platform.OS !== "android") {
      onChange(event, date);
      return;
    }
    if (activeStep.current !== step) return;
    if (event.type !== "set" || !date || !Number.isFinite(date.getTime())) {
      activeStep.current = null;
      onChange({ ...event, type: "dismissed" });
      return;
    }
    if (step === "date") {
      const next = new Date(date);
      next.setHours(value.getHours(), value.getMinutes(), 0, 0);
      selectedDate.current = next;
      activeStep.current = "time";
      setStep("time");
      return;
    }
    activeStep.current = null;
    const combined = new Date(selectedDate.current);
    combined.setHours(date.getHours(), date.getMinutes(), 0, 0);
    onChange({ ...event, nativeEvent: { ...event.nativeEvent, timestamp: combined.getTime() } }, combined);
  };

  return (
    <DateTimePicker
      key={step}
      value={Platform.OS === "android" && step === "time" ? selectedDate.current : value}
      mode={Platform.OS === "android" ? step : "datetime"}
      display={Platform.OS === "ios" ? "spinner" : "default"}
      disabled={disabled}
      onChange={handleChange}
    />
  );
}
