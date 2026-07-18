import { Pressable, Text, TextInput, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { DrawerNavLinks } from "@/components/drawer/DrawerNavLinks";
import { tap } from "@/lib/haptics";
import type { Theme } from "@/lib/theme";

import type { ConversationListStyles } from "./conversationListStyles";

type Props = {
  styles: ConversationListStyles;
  theme: Theme;
  paddingTop: number;
  searchOpen: boolean;
  searchQuery: string;
  searchInputRef: React.RefObject<TextInput | null>;
  onSearchChange: (text: string) => void;
  onOpenSearch: () => void;
  onCloseSearch: () => void;
  selectionMode?: boolean;
  selectedCount?: number;
  onExitSelection?: () => void;
  onSelectAll?: () => void;
  showIndicator: boolean;
  unseenCount: number;
  onProjects: () => void;
  onLists: () => void;
  onReminders: () => void;
};

export function DrawerHeader({
  styles: s,
  theme,
  paddingTop,
  searchOpen,
  searchQuery,
  searchInputRef,
  onSearchChange,
  onOpenSearch,
  onCloseSearch,
  selectionMode = false,
  selectedCount = 0,
  onExitSelection,
  onSelectAll,
  showIndicator,
  unseenCount,
  onProjects,
  onLists,
  onReminders,
}: Props) {
  const { t } = useTranslation();

  return (
    <View style={[s.topOverlay, { paddingTop }]} pointerEvents="box-none">
      <View style={s.header}>
        {searchOpen ? (
          <View style={s.searchBar}>
            <Ionicons name="search-outline" size={18} color={theme.textSecondary} />
            <TextInput
              ref={searchInputRef}
              style={s.searchInput}
              placeholder={t("search.placeholder")}
              placeholderTextColor={theme.textTertiary}
              value={searchQuery}
              onChangeText={onSearchChange}
              returnKeyType="search"
              autoCorrect={false}
              clearButtonMode="while-editing"
            />
            <Pressable
              hitSlop={8}
              onPress={() => {
                tap();
                onCloseSearch();
              }}
              style={s.searchCancel}
              accessibilityRole="button"
              accessibilityLabel={t("common.cancel")}
            >
              <Text style={s.searchCancelText}>{t("common.cancel")}</Text>
            </Pressable>
          </View>
        ) : selectionMode ? (
          <View style={s.selectionHeader}>
            <Pressable
              hitSlop={8}
              onPress={() => {
                tap();
                onExitSelection?.();
              }}
              style={s.selectionHeaderAction}
              accessibilityRole="button"
              accessibilityLabel={t("common.cancel")}
            >
              <Text style={s.selectionHeaderActionText}>{t("common.cancel")}</Text>
            </Pressable>
            <Text style={s.selectionHeaderTitle}>
              {t("drawer.selected_count", { count: selectedCount })}
            </Text>
            <Pressable
              hitSlop={8}
              onPress={() => {
                tap();
                onSelectAll?.();
              }}
              style={s.selectionHeaderAction}
              accessibilityRole="button"
              accessibilityLabel={t("drawer.select_all")}
            >
              <Text style={s.selectionHeaderActionText}>{t("drawer.select_all")}</Text>
            </Pressable>
          </View>
        ) : (
          <View style={s.logo}>
            <Text style={s.logoText}>{t("app.name")}</Text>
            <View style={s.headerActions}>
              <Pressable
                hitSlop={8}
                style={s.searchBtn}
                onPress={() => {
                  tap();
                  onOpenSearch();
                }}
                accessibilityRole="button"
                accessibilityLabel={t("search.open_accessibility")}
              >
                <Ionicons name="search-outline" size={20} color={theme.textSecondary} />
              </Pressable>
            </View>
          </View>
        )}
      </View>
      {/* Fixed above the scroll fade so Learning/Lists/Reminders aren't washed out. */}
      <DrawerNavLinks
        styles={s}
        theme={theme}
        showIndicator={showIndicator}
        unseenCount={unseenCount}
        onProjects={onProjects}
        onLists={onLists}
        onReminders={onReminders}
      />
    </View>
  );
}
