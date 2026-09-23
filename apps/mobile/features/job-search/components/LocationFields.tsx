import { useMemo, useState } from "react";
import {
  ActivityIndicator,
  Keyboard,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { FlashList } from "@shopify/flash-list";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { Icon } from "@/components/Icon";
import { requestDevicePlace } from "@/lib/deviceLocation";
import {
  COUNTRIES,
  matchCountry,
  matchSubdivision,
  searchPlaces,
  SUBDIVISIONS,
} from "@/features/job-search/model/geoData";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

export type PlaceValue = {
  country: string;
  region: string;
  city: string;
};

export const EMPTY_PLACE: PlaceValue = { country: "", region: "", city: "" };

/** "City, Region, Country" for the profile's single location string. */
export function composePlace(place: PlaceValue): string {
  return [place.city, place.region, place.country]
    .map((part) => part.trim())
    .filter(Boolean)
    .join(", ");
}

/**
 * Best-effort split of a stored free-text location back into picker parts.
 * Country/region snap to canonical names when recognized; anything left over
 * lands in city so nothing the user typed is lost.
 */
export function parsePlace(location: string): PlaceValue {
  const parts = location
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  if (parts.length === 0) return EMPTY_PLACE;

  let country = "";
  let region = "";
  const rest = [...parts];

  const last = rest[rest.length - 1];
  const matchedCountry = matchCountry(last);
  if (matchedCountry) {
    country = matchedCountry;
    rest.pop();
  }
  if (country && rest.length > 0) {
    const matchedRegion = matchSubdivision(country, rest[rest.length - 1]);
    if (matchedRegion) {
      region = matchedRegion;
      rest.pop();
    }
  }
  return { country, region, city: rest.join(", ") };
}

type GeoHint = "denied" | "error" | "expo_go" | null;

type Props = {
  value: PlaceValue;
  onChange: (next: PlaceValue) => void;
  disabled?: boolean;
};

/**
 * Structured location picker: device GPS fill, a worldwide country list, a
 * state dropdown where subdivisions are bundled (US/CA/AU) and free-text
 * region everywhere else.
 */
export function LocationFields({ value, onChange, disabled }: Props) {
  const C = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(C), [C]);
  const [locating, setLocating] = useState(false);
  const [geoHint, setGeoHint] = useState<GeoHint>(null);
  const [picker, setPicker] = useState<"country" | "region" | null>(null);
  const [pickerQuery, setPickerQuery] = useState("");

  const regions = value.country ? (SUBDIVISIONS[value.country] ?? null) : null;
  const pickerItems = useMemo(() => {
    const list = picker === "region" ? (regions ?? []) : COUNTRIES;
    return searchPlaces(list, pickerQuery);
  }, [picker, pickerQuery, regions]);

  const fillFromDevice = async () => {
    if (disabled || locating) return;
    Keyboard.dismiss();
    setLocating(true);
    setGeoHint(null);
    try {
      const result = await requestDevicePlace();
      if (result.status === "granted") {
        const { place } = result;
        if (!place.country && !place.region && !place.city) {
          // Permission was fine but the geocoder returned nothing (e.g. no
          // simulated location) — say so instead of wiping the fields.
          setGeoHint("error");
          return;
        }
        const country = place.country
          ? (matchCountry(place.country) ?? place.country)
          : "";
        const region =
          country && place.region
            ? (matchSubdivision(country, place.region) ?? place.region)
            : "";
        onChange({ country, region, city: place.city ?? "" });
      } else {
        setGeoHint(result.status === "expo_go" ? "expo_go" : result.status === "error" ? "error" : "denied");
      }
    } finally {
      setLocating(false);
    }
  };

  const openPicker = (which: "country" | "region") => {
    if (disabled) return;
    Keyboard.dismiss();
    setPickerQuery("");
    setPicker(which);
  };

  const selectItem = (item: string) => {
    if (picker === "country") {
      // Changing country invalidates a region from the previous one.
      onChange({ ...value, country: item, region: "" });
    } else {
      onChange({ ...value, region: item });
    }
    setPicker(null);
  };

  const geoHintText =
    geoHint === "denied"
      ? t("my_job.location_denied")
      : geoHint === "expo_go"
        ? t("settings.location_expo_go")
        : geoHint === "error"
          ? t("my_job.location_unavailable")
          : null;

  return (
    <View style={s.wrap}>
      <Pressable
        style={({ pressed }) => [s.geoRow, pressed && s.pressed, disabled && s.disabled]}
        onPress={() => void fillFromDevice()}
        disabled={disabled || locating}
        accessibilityRole="button"
        accessibilityLabel={t("settings.use_current_location")}
      >
        <View style={s.geoIcon}>
          {locating ? (
            <ActivityIndicator size="small" color={C.primary} />
          ) : (
            <Icon name="locate-outline" size={20} color={C.primary} />
          )}
        </View>
        <Text style={s.geoText}>
          {locating ? t("my_job.location_locating") : t("settings.use_current_location")}
        </Text>
      </Pressable>
      {geoHintText ? <Text style={s.hint}>{geoHintText}</Text> : null}

      <View style={s.fieldGroup}>
        <Text style={s.label}>{t("my_job.location_country_label")}</Text>
        <Pressable
          style={({ pressed }) => [s.selectRow, pressed && s.pressed, disabled && s.disabled]}
          onPress={() => openPicker("country")}
          disabled={disabled}
          accessibilityRole="button"
        >
          <Text
            style={value.country ? s.selectValue : s.selectPlaceholder}
            numberOfLines={1}
          >
            {value.country || t("my_job.location_country_placeholder")}
          </Text>
          <Icon name="chevron-down" size={18} color={C.textTertiary} />
        </Pressable>
      </View>

      <View style={s.fieldGroup}>
        <Text style={s.label}>{t("my_job.location_region_label")}</Text>
        {regions ? (
          <Pressable
            style={({ pressed }) => [s.selectRow, pressed && s.pressed, disabled && s.disabled]}
            onPress={() => openPicker("region")}
            disabled={disabled}
            accessibilityRole="button"
          >
            <Text
              style={value.region ? s.selectValue : s.selectPlaceholder}
              numberOfLines={1}
            >
              {value.region || t("my_job.location_region_placeholder")}
            </Text>
            <Icon name="chevron-down" size={18} color={C.textTertiary} />
          </Pressable>
        ) : (
          <TextInput
            style={s.input}
            value={value.region}
            onChangeText={(region) => onChange({ ...value, region })}
            placeholder={t("my_job.location_region_placeholder")}
            placeholderTextColor={C.textDisabled}
            editable={!disabled}
            autoCapitalize="words"
          />
        )}
      </View>

      <View style={s.fieldGroup}>
        <Text style={s.label}>{t("my_job.location_city_label")}</Text>
        <TextInput
          style={s.input}
          value={value.city}
          onChangeText={(city) => onChange({ ...value, city })}
          placeholderTextColor={C.textDisabled}
          editable={!disabled}
          autoCapitalize="words"
        />
      </View>

      <AppSheet
        visible={picker !== null}
        onClose={() => setPicker(null)}
        variant="bottom"
        withHandle
        floating
        keyboardAvoiding
        minBottomPadding={12}
        contentContainerStyle={s.sheetContent}
      >
        <Text style={s.sheetTitle}>
          {picker === "region"
            ? t("my_job.location_region_label")
            : t("my_job.location_country_label")}
        </Text>
        <View style={s.sheetSearchRow}>
          <Icon name="search" size={18} color={C.textTertiary} />
          <TextInput
            style={s.sheetSearch}
            value={pickerQuery}
            onChangeText={setPickerQuery}
            placeholder={t("my_job.location_search_placeholder")}
            placeholderTextColor={C.textDisabled}
            autoCapitalize="words"
            autoCorrect={false}
          />
        </View>
        <View style={s.sheetList}>
          <FlashList
            data={pickerItems}
            keyExtractor={(item) => item}
            keyboardShouldPersistTaps="handled"
            renderItem={({ item }) => {
              const selected =
                picker === "region" ? item === value.region : item === value.country;
              return (
                <Pressable
                  style={({ pressed }) => [s.sheetRow, pressed && s.suggestionPressed]}
                  onPress={() => selectItem(item)}
                  accessibilityRole="button"
                  accessibilityState={{ selected }}
                >
                  <Text
                    style={[s.sheetRowText, selected && s.sheetRowTextSelected]}
                    numberOfLines={1}
                  >
                    {item}
                  </Text>
                  {selected ? (
                    <Icon name="checkmark" size={18} color={C.primary} />
                  ) : null}
                </Pressable>
              );
            }}
          />
        </View>
      </AppSheet>
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    wrap: { gap: Space.sm },
    geoRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      minHeight: 48,
      borderRadius: Radius.xl,
      backgroundColor: C.primaryLight,
      paddingHorizontal: Space.md,
      alignSelf: "flex-start",
      paddingRight: Space.lg,
    },
    geoIcon: {
      width: 28,
      height: 28,
      alignItems: "center",
      justifyContent: "center",
    },
    geoText: { ...Type.secondary, fontWeight: "600", color: C.primary },
    hint: { ...Type.caption, color: C.textTertiary },
    fieldGroup: { gap: Space.xs },
    label: { ...Type.label, color: C.text },
    selectRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      minHeight: 54,
      borderRadius: Radius.xl,
      backgroundColor: C.surface,
      paddingHorizontal: Space.md,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
    },
    selectValue: { ...Type.body, color: C.text, flex: 1 },
    selectPlaceholder: { ...Type.body, color: C.textDisabled, flex: 1 },
    input: {
      ...Type.body,
      minHeight: 54,
      borderRadius: Radius.xl,
      backgroundColor: C.surface,
      color: C.text,
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
    },
    sheetContent: { gap: Space.sm },
    sheetTitle: {
      ...Type.label,
      color: C.text,
      textAlign: "center",
      paddingBottom: Space.xxs,
    },
    sheetSearchRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      minHeight: 46,
      borderRadius: Radius.lg,
      backgroundColor: C.surfaceAlt,
      paddingHorizontal: Space.md,
    },
    sheetSearch: {
      ...Type.body,
      flex: 1,
      color: C.text,
      paddingVertical: Space.xs,
    },
    sheetList: { height: 340 },
    sheetRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      minHeight: 48,
      paddingHorizontal: Space.sm,
      borderRadius: Radius.md,
    },
    suggestionPressed: { backgroundColor: C.surfaceAlt },
    sheetRowText: { ...Type.body, color: C.text, flex: 1 },
    sheetRowTextSelected: { color: C.primary, fontWeight: "600" },
    pressed: { opacity: 0.72 },
    disabled: { opacity: 0.45 },
  });
}
