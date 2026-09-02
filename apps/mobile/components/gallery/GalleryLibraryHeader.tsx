import { useMemo } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { tap } from "@/lib/haptics";
import { type GalleryFilter } from "@/lib/gallery";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Props = {
  filter: GalleryFilter;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  onFilterChange: (filter: GalleryFilter) => void;
};

export function GalleryLibraryHeader({
  filter,
  searchQuery,
  onSearchChange,
  onFilterChange,
}: Props) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const filters: { key: GalleryFilter; label: string }[] = [
    { key: "all", label: t("gallery.filter.all") },
    { key: "generated", label: t("gallery.filter.generated") },
    { key: "uploaded", label: t("gallery.filter.uploaded") },
    { key: "files", label: t("gallery.filter.files") },
  ];

  return (
    <View style={s.header}>
      <View style={s.searchBar}>
        <Icon name="search-outline" size={16} color={C.textTertiary} />
        <TextInput
          style={s.searchInput}
          placeholder={t("gallery.search_placeholder")}
          placeholderTextColor={C.textDisabled}
          value={searchQuery}
          onChangeText={onSearchChange}
          autoCorrect={false}
          returnKeyType="search"
        />
        {searchQuery.length > 0 ? (
          <Pressable
            onPress={() => onSearchChange("")}
            accessibilityRole="button"
            accessibilityLabel={t("gallery.search_clear_a11y")}
            testID="gallery-search-clear"
            hitSlop={8}
          >
            <Icon name="close-circle-outline" size={18} color={C.textTertiary} />
          </Pressable>
        ) : null}
      </View>
      <View style={s.tabs}>
        {filters.map((tab) => {
          const active = tab.key === filter;
          return (
            <Pressable
              key={tab.key}
              style={[s.tab, active && s.tabActive]}
              onPress={() => {
                tap();
                onFilterChange(tab.key);
              }}
              accessibilityRole="button"
              accessibilityLabel={tab.label}
              accessibilityState={{ selected: active }}
            >
              <Text style={[s.tabText, active && s.tabTextActive]}>{tab.label}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    header: {
      paddingHorizontal: Space.md,
      paddingTop: Space.sm,
      paddingBottom: Space.sm,
    },
    searchBar: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
      minHeight: 44,
      paddingHorizontal: 14,
      borderRadius: 20,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
      backgroundColor: C.surfaceAlt,
      marginBottom: Space.sm,
    },
    searchInput: {
      flex: 1,
      ...Type.body,
      fontSize: 15,
      padding: 0,
      color: C.text,
    },
    tabs: {
      flexDirection: "row",
      flexWrap: "wrap",
      gap: Space.xs,
    },
    tab: {
      minHeight: 44,
      justifyContent: "center",
      paddingVertical: Space.xs,
      paddingHorizontal: 12,
      borderRadius: 20,
      flexGrow: 0,
      flexShrink: 0,
    },
    tabActive: {
      backgroundColor: C.surfaceAlt,
    },
    tabText: {
      ...Type.label,
      color: C.textSecondary,
      fontWeight: "500",
    },
    tabTextActive: {
      color: C.text,
      fontWeight: "600",
    },
  });
}
