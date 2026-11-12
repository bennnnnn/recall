import { Image, Pressable, Text, View, type TextInputInstance } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/ui/icons/Icon";
import { tap } from "@/lib/haptics";
import { IconSize } from "@/ui/icons/sizes";
import type { Theme } from "@/lib/theme";
import { SearchField } from "@/ui/controls/SearchField";

import type { ConversationListStyles } from "./conversationListStyles";

const APP_ICON = require("@/assets/images/icon.png") as number;

type Props = {
  styles: ConversationListStyles;
  theme: Theme;
  paddingTop: number;
  searchOpen: boolean;
  searchQuery: string;
  searchInputRef: React.RefObject<TextInputInstance | null>;
  onSearchChange: (text: string) => void;
  onOpenSearch: () => void;
  onCloseSearch: () => void;
  selectionMode?: boolean;
  selectedCount?: number;
  onExitSelection?: () => void;
  onSelectAll?: () => void;
};

/**
 * The drawer's top bar: Recall's mark at the left, search at the right (the owner's layout,
 * 2026-11-11). Tapped, search becomes the field across the bar; selecting chats, the bar
 * holds Cancel, the count and Select all.
 */
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
}: Props) {
  const { t } = useTranslation();

  return (
    <View style={[s.topOverlay, { paddingTop }]} pointerEvents="box-none">
      <View style={s.header}>
        {selectionMode ? (
          <View style={s.selectionHeader}>
            <Pressable
              hitSlop={11}
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
              hitSlop={11}
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
        ) : searchOpen ? (
          <SearchField
            style={s.headerSearch}
            inputRef={searchInputRef}
            value={searchQuery}
            onChangeText={onSearchChange}
            placeholder={t("search.placeholder")}
            clearButtonMode="while-editing"
            trailing={
              <Pressable
                hitSlop={{ top: 13, bottom: 13, left: 8, right: 8 }}
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
            }
          />
        ) : (
          <View style={s.logo}>
            <Image
              source={APP_ICON}
              style={s.appMark}
              accessibilityRole="image"
              accessibilityLabel={t("app.name")}
            />
            <Pressable
              style={s.headerIconBtn}
              onPress={() => {
                tap();
                onOpenSearch();
              }}
              accessibilityRole="search"
              accessibilityLabel={t("search.open_accessibility")}
            >
              <Icon name="search" size={IconSize.md} color={theme.text} />
            </Pressable>
          </View>
        )}
      </View>
    </View>
  );
}
