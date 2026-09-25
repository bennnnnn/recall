import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/ui/icons/Icon";
import { SearchField } from "@/ui/controls/SearchField";
import { tap } from "@/lib/haptics";
import { type GalleryFilter } from "@/features/attachments/model/gallery";
import { type GalleryLayout } from "@/features/attachments/model/galleryLayout";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import { IconSize } from "@/lib/icons";
import { Radius } from "@/lib/radius";

type Props = {
  filter: GalleryFilter;
  searchQuery: string;
  layout: GalleryLayout;
  onSearchChange: (query: string) => void;
  onFilterChange: (filter: GalleryFilter) => void;
  onToggleLayout: () => void;
};

export function GalleryLibraryHeader({
  filter,
  searchQuery,
  layout,
  onSearchChange,
  onFilterChange,
  onToggleLayout,
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
      <SearchField
        style={s.searchField}
        value={searchQuery}
        onChangeText={onSearchChange}
        placeholder={t("gallery.search_placeholder")}
        onClear={() => onSearchChange("")}
        clearAccessibilityLabel={t("gallery.search_clear_a11y")}
        clearTestID="gallery-search-clear"
      />
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
        <Pressable
          onPress={onToggleLayout}
          accessibilityRole="button"
          accessibilityLabel={
            layout === "grid"
              ? t("gallery.layout_column_a11y")
              : t("gallery.layout_grid_a11y")
          }
          style={s.layoutToggle}
          testID="gallery-layout-toggle"
        >
          <Icon
            name={layout === "grid" ? "list-outline" : "grid-outline"}
            size={IconSize.md}
            color={C.textSecondary}
          />
        </Pressable>
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
    searchField: { marginBottom: Space.sm },
    tabs: {
      flexDirection: "row",
      flexWrap: "wrap",
      alignItems: "center",
      gap: Space.xs,
    },
    tab: {
      minHeight: 44,
      justifyContent: "center",
      paddingVertical: Space.xs,
      paddingHorizontal: Space.sm,
      borderRadius: Radius.sheet,
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
    layoutToggle: {
      minHeight: 44,
      minWidth: 44,
      alignItems: "center",
      justifyContent: "center",
    },
  });
}
