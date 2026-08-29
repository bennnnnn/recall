import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { Icon } from "@/components/Icon";
import { openPlaceLink } from "@/lib/openPlaceLink";
import { PlaceItem, resolvePlaceLinkUrl } from "@/lib/placesList";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  places: PlaceItem[];
};

export function PlacesListBlock({ places }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [selected, setSelected] = useState<PlaceItem | null>(null);

  if (places.length === 0) return null;

  return (
    <View style={s.list}>
      {places.map((place, index) => {
        return (
          <View key={`${place.name}-${index}`} style={s.row}>
            <Text style={s.index}>{index + 1}.</Text>
            <View style={s.body}>
              <Pressable
                onPress={() => setSelected(place)}
                accessibilityRole="button"
                accessibilityLabel={t("places.show_details_a11y", { name: place.name })}
              >
                <Text style={s.name} numberOfLines={2}>
                  {place.name}
                </Text>
              </Pressable>
              {place.note ? (
                <Text style={s.note} numberOfLines={3}>
                  {place.note}
                </Text>
              ) : null}
              <View style={s.metaRow}>
                {place.price ? <Text style={s.price}>{place.price}</Text> : null}
                {place.address ? (
                  <Text style={s.address} numberOfLines={2}>
                    {place.address}
                  </Text>
                ) : null}
              </View>
            </View>
          </View>
        );
      })}

      <PlaceDetailsSheet
        place={selected}
        onClose={() => setSelected(null)}
      />
    </View>
  );
}

function PlaceDetailsSheet({
  place,
  onClose,
}: {
  place: PlaceItem | null;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSheetStyles(theme), [theme]);
  const visible = place !== null;

  const openInMaps = () => {
    if (!place) return;
    const url = resolvePlaceLinkUrl(place);
    void openPlaceLink(url, place.name);
  };

  return (
    <AppSheet
      visible={visible}
      onClose={onClose}
      minBottomPadding={16}
      contentContainerStyle={s.sheet}
    >
      {place ? (
        <>
          <Text style={s.title} numberOfLines={3}>
            {place.name}
          </Text>
          {place.note ? (
            <Text style={s.note} numberOfLines={5}>
              {place.note}
            </Text>
          ) : null}
          <View style={s.metaRow}>
            {place.price ? <Text style={s.price}>{place.price}</Text> : null}
            {place.address ? (
              <Text style={s.address} numberOfLines={3}>
                {place.address}
              </Text>
            ) : null}
          </View>
          <Pressable style={s.openBtn} onPress={openInMaps}>
            <Icon name="map-outline" size={20} color={theme.onPrimary} />
            <Text style={s.openBtnText}>{t("places.open_in_maps")}</Text>
          </Pressable>
        </>
      ) : null}
    </AppSheet>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    list: {
      marginVertical: 8,
      gap: 10,
    },
    row: {
      flexDirection: "row",
      alignItems: "flex-start",
      gap: 8,
    },
    index: {
      width: 22,
      paddingTop: 1,
      fontSize: 16,
      lineHeight: 22,
      fontWeight: "600",
      color: t.text,
    },
    body: {
      flex: 1,
      minWidth: 0,
      gap: 4,
    },
    name: {
      fontSize: 16,
      lineHeight: 22,
      fontWeight: "600",
      color: t.text,
      textDecorationLine: "underline",
      textDecorationStyle: "dotted",
      textDecorationColor: t.textSecondary,
    },
    note: {
      fontSize: 14,
      lineHeight: 20,
      color: t.textSecondary,
    },
    metaRow: {
      flexDirection: "row",
      flexWrap: "wrap",
      alignItems: "center",
      gap: 8,
    },
    price: {
      fontSize: 13,
      fontWeight: "600",
      color: t.textSecondary,
    },
    address: {
      flexShrink: 1,
      fontSize: 13,
      lineHeight: 18,
      color: t.textTertiary,
    },
  });
}

function makeSheetStyles(t: Theme) {
  return StyleSheet.create({
    sheet: {
      paddingHorizontal: 20,
      gap: 10,
    },
    title: {
      fontSize: 18,
      fontWeight: "700",
      color: t.text,
      lineHeight: 23,
    },
    note: {
      fontSize: 15,
      lineHeight: 21,
      color: t.textSecondary,
    },
    metaRow: {
      flexDirection: "row",
      flexWrap: "wrap",
      alignItems: "center",
      gap: 8,
    },
    price: {
      fontSize: 14,
      fontWeight: "600",
      color: t.textSecondary,
    },
    address: {
      flexShrink: 1,
      fontSize: 14,
      lineHeight: 19,
      color: t.textTertiary,
    },
    openBtn: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
      backgroundColor: t.primary,
      borderRadius: 14,
      paddingVertical: 14,
      marginTop: 6,
    },
    openBtnText: {
      fontSize: 16,
      fontWeight: "700",
      color: t.onPrimary,
    },
  });
}
