import { Pressable, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Avatar } from "@/components/Avatar";
import { NewChatIcon } from "@/components/NewChatIcon";
import { useAuth } from "@/contexts/AuthContext";
import { tap } from "@/lib/haptics";
import type { Theme } from "@/lib/theme";

import type { ConversationListStyles } from "./conversationListStyles";

type Props = {
  styles: ConversationListStyles;
  theme: Theme;
  paddingBottom: number;
  onNewChat: () => void;
  onSettings: () => void;
};

export function DrawerFooter({
  styles: s,
  theme,
  paddingBottom,
  onNewChat,
  onSettings,
}: Props) {
  const { t } = useTranslation();
  const { user, token } = useAuth();

  return (
    <View style={[s.footer, { paddingBottom }]} pointerEvents="box-none">
      <Pressable
        style={s.footerNewChat}
        onPress={() => {
          tap();
          onNewChat();
        }}
        accessibilityRole="button"
        accessibilityLabel={t("drawer.new_chat")}
      >
        <NewChatIcon size={18} color={theme.onPrimary} />
        <Text style={s.footerNewChatText}>{t("drawer.new_chat")}</Text>
      </Pressable>
      <Pressable
        style={s.profileBtn}
        onPress={() => {
          tap();
          onSettings();
        }}
        accessibilityRole="button"
        accessibilityLabel={t("settings.title")}
      >
        <Avatar name={user?.name ?? null} uri={user?.avatar_url} token={token} size={36} />
      </Pressable>
    </View>
  );
}
