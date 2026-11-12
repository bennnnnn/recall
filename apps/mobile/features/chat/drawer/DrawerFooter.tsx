import { Pressable, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Avatar } from "@/components/Avatar";
import { useAuth } from "@/contexts/AuthContext";
import { tap } from "@/lib/haptics";
import { getDisplayName } from "@/lib/profile";
import type { Theme } from "@/lib/theme";
import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";

import type { ConversationListStyles } from "./conversationListStyles";

type Props = {
  styles: ConversationListStyles;
  theme: Theme;
  paddingBottom: number;
  onAccount: () => void;
  onNewChat: () => void;
};

/**
 * The drawer's bottom bar (the owner's layout, 2026-11-11): the account at the left, its
 * picture and name, which opens Settings; New chat at the right, in reach of the thumb.
 */
export function DrawerFooter({ styles: s, theme, paddingBottom, onAccount, onNewChat }: Props) {
  const { t, i18n } = useTranslation();
  const { user, token } = useAuth();
  const name = getDisplayName(user?.name, t("common.you"), i18n.language);

  return (
    <View testID="drawer-footer" style={[s.footer, s.chromeBar, { paddingBottom }]}>
      <Pressable
        style={s.accountRow}
        onPress={() => {
          tap();
          onAccount();
        }}
        accessibilityRole="button"
        accessibilityLabel={name}
        accessibilityHint={t("settings.title")}
      >
        <Avatar name={user?.name ?? null} uri={user?.avatar_url} token={token} size={32} />
        <Text style={s.accountName} numberOfLines={1}>
          {name}
        </Text>
      </Pressable>
      <Pressable
        style={s.newChatBtn}
        hitSlop={6}
        onPress={() => {
          tap();
          onNewChat();
        }}
        accessibilityRole="button"
        accessibilityLabel={t("chat.new_chat")}
      >
        <Icon name="edit" size={IconSize.md} color={theme.onPrimary} />
      </Pressable>
    </View>
  );
}
