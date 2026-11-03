import { Pressable, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { tap } from "@/lib/haptics";
import type { Theme } from "@/lib/theme";

import type { ConversationListStyles } from "./conversationListStyles";
import { IconSize } from "@/ui/icons/sizes";
import { Icon } from "@/ui/icons/Icon";

type Props = {
  styles: ConversationListStyles;
  theme: Theme;
  paddingBottom: number;
  onOpenSearch: () => void;
};

/** The drawer's bottom row: the app's name, and search (its field opens at the top). */
export function DrawerFooter({ styles: s, theme, paddingBottom, onOpenSearch }: Props) {
  const { t } = useTranslation();

  return (
    <View style={[s.footer, { paddingBottom }]} pointerEvents="box-none">
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
          <Icon name="search" size={IconSize.sm} color={theme.text} />
        </Pressable>
      </View>
    </View>
  );
}
