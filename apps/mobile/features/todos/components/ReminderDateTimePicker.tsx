import { useLayoutEffect, useRef } from "react";
import { Platform } from "react-native";
import DateTimePicker, { type DateTimePickerEvent } from "@react-native-community/datetimepicker";

type Props = {
  value: Date;
  mode: "date" | "time" | "datetime";
  disabled?: boolean;
  onChange: (event: DateTimePickerEvent, date?: Date) => void;
};

/**
 * One native wheel. Date mode includes the year. Time is a separate wheel.
 * Android dialogs close themselves; iOS stays in the choice card until Done.
 */
export function ReminderDateTimePicker({ value, mode, disabled, onChange }: Props) {
  const mounted = useRef(false);
  const disabledRef = useRef(disabled);
  disabledRef.current = disabled;
  useLayoutEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const handleChange = (event: DateTimePickerEvent, date?: Date) => {
    if (!mounted.current || disabledRef.current) return;
    if (
      Platform.OS === "android" &&
      (event.type !== "set" || !date || !Number.isFinite(date.getTime()))
    ) {
      onChange({ ...event, type: "dismissed" });
      return;
    }
    onChange(event, date);
  };

  return (
    <DateTimePicker
      value={value}
      mode={mode}
      display={Platform.OS === "ios" ? "spinner" : "default"}
      disabled={disabled}
      onChange={handleChange}
    />
  );
}
