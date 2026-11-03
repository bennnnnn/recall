import { Pressable, Text, View, type TextInputInstance } from "react-native";
import { useTranslation } from "react-i18next";

import { tap } from "@/lib/haptics";
import { Space } from "@/lib/space";
import type { Theme } from "@/lib/theme";
import { SearchField } from "@/ui/controls/SearchField";

import type { ConversationListStyles } from "./conversationListStyles";
import { IconSize } from "@/ui/icons/sizes";
import { Icon } from "@/ui/icons/Icon";

type Props = {
  styles: ConversationListStyles;
  theme: Theme;
  paddingBottom: number;
  /** The open keyboard's height: the open field sits on it. */
  keyboardHeight: number;
  searchOpen: boolean;
  searchQuery: string;
  searchInputRef: React.RefObject<TextInputInstance | null>;
  onSearchChange: (text: string) => void;
  onOpenSearch: () => void;
  onCloseSearch: () => void;
};

/**
 * The drawer's bottom row: one search bar, in reach of the thumb. Tapped, it becomes
 * the field in place, above the keyboard.
 */
export function DrawerFooter({
  styles: s,
  theme,
  paddingBottom,
  keyboardHeight,
  searchOpen,
  searchQuery,
  searchInputRef,
  onSearchChange,
  onOpenSearch,
  onCloseSearch,
}: Props) {
  const { t } = useTranslation();
  const lifted = searchOpen && keyboardHeight > 0;

  return (
    <View
      testID="drawer-footer"
      style={[s.footer, lifted ? { bottom: keyboardHeight, paddingBottom: Space.xs } : { paddingBottom }]}
      pointerEvents="box-none"
    >
      {searchOpen ? (
        <SearchField
          style={s.footerSearch}
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
        <Pressable
          style={s.searchBar}
          onPress={() => {
            tap();
            onOpenSearch();
          }}
          accessibilityRole="search"
          accessibilityLabel={t("search.open_accessibility")}
        >
          <Icon name="search" size={IconSize.sm} color={theme.text} />
          <Text style={s.searchBarText} numberOfLines={1}>
            {t("search.placeholder")}
          </Text>
        </Pressable>
      )}
    </View>
  );
}
