import { useEffect, useState } from "react";
import { Platform, StyleSheet, View } from "react-native";
import DateTimePicker, {
  type DateTimePickerEvent,
} from "@react-native-community/datetimepicker";

import { AppSheet } from "@/components/AppSheet";
import { SheetFormHeader } from "@/components/SheetFormHeader";
import { Space } from "@/lib/space";

type Props = {
  visible: boolean;
  title: string;
  valueMinutes: number;
  cancelLabel: string;
  saveLabel: string;
  saving?: boolean;
  onClose: () => void;
  onSave: (minutes: number) => void;
};

function dateFromMinute(minutes: number): Date {
  const date = new Date();
  date.setHours(Math.floor(minutes / 60), minutes % 60, 0, 0);
  return date;
}

function minuteFromDate(date: Date): number {
  return date.getHours() * 60 + date.getMinutes();
}

/**
 * Time-only picker used by quiet hours.
 *
 * iOS keeps spinner changes in a local draft until Done. Android keeps the
 * platform dialog behavior and commits one completed selection immediately.
 */
export function TimePickerSheet({
  visible,
  title,
  valueMinutes,
  cancelLabel,
  saveLabel,
  saving = false,
  onClose,
  onSave,
}: Props) {
  const [draft, setDraft] = useState(() => dateFromMinute(valueMinutes));

  useEffect(() => {
    if (visible) setDraft(dateFromMinute(valueMinutes));
  }, [visible, valueMinutes]);

  const onAndroidChange = (event: DateTimePickerEvent, date?: Date) => {
    onClose();
    if (event.type === "dismissed" || !date) return;
    onSave(minuteFromDate(date));
  };

  if (Platform.OS === "android") {
    return visible ? (
      <DateTimePicker
        mode="time"
        value={draft}
        onChange={onAndroidChange}
        display="default"
      />
    ) : null;
  }

  return (
    <AppSheet
      visible={visible && Platform.OS === "ios"}
      onClose={onClose}
      variant="bottom"
      withHandle={false}
      contentContainerStyle={styles.sheet}
    >
      <SheetFormHeader
        title={title}
        onCancel={onClose}
        onSave={() => onSave(minuteFromDate(draft))}
        cancelLabel={cancelLabel}
        saveLabel={saveLabel}
        saving={saving}
      />
      <View style={styles.pickerWrap}>
        <DateTimePicker
          mode="time"
          value={draft}
          onChange={(_event, date) => {
            if (date) setDraft(date);
          }}
          display="spinner"
        />
      </View>
    </AppSheet>
  );
}

const styles = StyleSheet.create({
  sheet: { paddingHorizontal: 0, paddingTop: 0 },
  pickerWrap: { alignItems: "center", paddingVertical: Space.sm },
});
