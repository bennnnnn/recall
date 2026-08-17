import { Pressable, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { NewChatIcon } from "@/components/NewChatIcon";
import { tap } from "@/lib/haptics";
import { filledIconName } from "@/lib/icons";
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
        style={s.settingsBtn}
        onPress={() => {
          tap();
          onSettings();
        }}
        accessibilityRole="button"
        accessibilityLabel={t("settings.title")}
      >
        <Ionicons
          name={filledIconName("settings-outline")}
          size={22}
          color={theme.onPrimary}
        />
      </Pressable>
    </View>
  );
}
