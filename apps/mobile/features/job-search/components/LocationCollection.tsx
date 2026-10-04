import { useState } from "react";
import { Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { LocationFields, EMPTY_PLACE, composePlace, type PlaceValue } from "./LocationFields";
import { FieldLabel, useSetupStyles } from "./setup/setupShared";
import { Button } from "@/ui/controls/Button";
import { Sheet } from "@/ui/overlay/Sheet";

export function LocationCollection({ included, excluded, onIncluded, onExcluded, disabled }: {
  included: PlaceValue[]; excluded: PlaceValue[];
  onIncluded: (places: PlaceValue[]) => void; onExcluded: (places: PlaceValue[]) => void;
  disabled: boolean;
}) {
  const { t } = useTranslation();
  const s = useSetupStyles();
  const [kind, setKind] = useState<"included" | "excluded" | null>(null);
  const [draft, setDraft] = useState<PlaceValue>(EMPTY_PLACE);
  const add = () => {
    if (!draft.country) return;
    const values = kind === "included" ? included : excluded;
    const next = [...values.filter(place => composePlace(place) !== composePlace(draft)), draft];
    if (kind === "included") {
      onIncluded(next);
      onExcluded(excluded.filter(place => composePlace(place) !== composePlace(draft)));
    } else {
      onExcluded(next);
      onIncluded(included.filter(place => composePlace(place) !== composePlace(draft)));
    }
    setKind(null);
  };
  return <>
    {(["included", "excluded"] as const).map(type => <View key={type} style={s.fieldGroup}>
      <FieldLabel>{t(type === "included" ? "my_job.additional_locations" : "my_job.excluded_locations")}</FieldLabel>
      {(type === "included" ? included : excluded).map((place, index) => <View key={composePlace(place)} style={s.chipRow}>
        <Text style={s.helper}>{composePlace(place)}</Text>
        <Button title={t("my_job.remove_location")} variant="ghost" disabled={disabled} onPress={() => {
          const next = (type === "included" ? included : excluded).filter((_, i) => i !== index);
          if (type === "included") onIncluded(next); else onExcluded(next);
        }} />
      </View>)}
      <Button title={t(type === "included" ? "my_job.add_location" : "my_job.exclude_location")}
        variant="outline" icon="plus" disabled={disabled || (type === "included" ? included : excluded).length >= 19}
        onPress={() => { setDraft(EMPTY_PLACE); setKind(type); }} />
    </View>)}
    <Sheet visible={kind !== null} onClose={() => setKind(null)}>
      <FieldLabel>{t("my_job.location_label")}</FieldLabel>
      <LocationFields value={draft} onChange={setDraft} />
      <Button title={t("common.add")} disabled={!draft.country} onPress={add} />
    </Sheet>
  </>;
}
