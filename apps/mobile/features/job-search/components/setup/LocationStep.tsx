import { View } from "react-native";
import { useTranslation } from "react-i18next";

import {
  LocationFields,
  type PlaceValue,
} from "@/features/job-search/components/LocationFields";
import type { JobSearchWorkMode } from "@/lib/api";

import {
  FieldLabel,
  SelectChip,
  useSetupStyles,
  WORK_MODE_VALUES,
} from "./setupShared";

type Props = {
  place: PlaceValue;
  workModes: JobSearchWorkMode[];
  busy: boolean;
  onPlaceChange: (place: PlaceValue) => void;
  onWorkModePress: (mode: JobSearchWorkMode) => void;
};

export function LocationStep({
  place,
  workModes,
  busy,
  onPlaceChange,
  onWorkModePress,
}: Props) {
  const { t } = useTranslation();
  const s = useSetupStyles();

  return (
    <>
      <View style={s.fieldGroup}>
        <FieldLabel>{t("my_job.location_label")}</FieldLabel>
        <LocationFields value={place} onChange={onPlaceChange} disabled={busy} />
      </View>

      <View style={s.fieldGroup}>
        <FieldLabel>{t("my_job.work_mode_label")}</FieldLabel>
        <View style={s.chipRow}>
          {WORK_MODE_VALUES.map((value) => (
            <SelectChip
              key={value}
              value={value}
              label={t(`my_job.work_${value}`)}
              selected={workModes.includes(value)}
              onPress={onWorkModePress}
              disabled={busy}
            />
          ))}
        </View>
      </View>
    </>
  );
}
