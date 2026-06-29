import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { openPlaceLink } from "@/lib/openPlaceLink";
import { PlaceItem, resolvePlaceLinkUrl } from "@/lib/placesList";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  places: PlaceItem[];
};

export function PlacesListBlock({ places }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  if (places.length === 0) return null;

  return (
    <View style={s.list}>
      {places.map((place, index) => {
        const mapsUrl = resolvePlaceLinkUrl(place);
        return (
          <View key={`${mapsUrl}-${index}`} style={s.row}>
            <Text style={s.index}>{index + 1}.</Text>
            <View style={s.body}>
              <Pressable
                onPress={() => openPlaceLink(mapsUrl, place.name)}
                accessibilityRole="link"
                accessibilityLabel={`${place.name}, open in maps`}
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
    </View>
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
