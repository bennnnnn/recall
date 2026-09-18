import { useCallback, useMemo } from "react";
import { FlatList, View } from "react-native";
import { useTranslation } from "react-i18next";

import { makeAutomationsStyles } from "@/components/automations/automationsStyles";
import { MessageBubble } from "@/components/MessageBubble";
import { StateView } from "@/components/StateView";
import { useAuth } from "@/contexts/AuthContext";
import { api, type Message } from "@/lib/api";
import { useTheme } from "@/lib/theme";

/** Read-only run history for one automation — no send, no regenerate, no
 * streaming. Reuses MessageBubble so rich fences (search sources, tables,
 * etc.) render exactly like a normal chat reply. */
export function AutomationTranscript({
  chatId,
  messages,
}: {
  chatId: string;
  messages: Message[];
}) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const C = useTheme();
  const s = useMemo(() => makeAutomationsStyles(C), [C]);

  const onFeedback = useCallback(
    (messageId: string, feedback: "up" | "down" | null) => {
      if (!token) return;
      void api.setMessageFeedback(token, chatId, messageId, feedback).catch(() => undefined);
    },
    [token, chatId],
  );

  if (messages.length === 0) {
    return (
      <StateView variant="empty" icon="time-outline" title={t("automations.transcript_empty")} />
    );
  }

  return (
    <FlatList
      style={s.transcriptList}
      contentContainerStyle={s.transcriptContent}
      data={messages}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => (
        <View>
          <MessageBubble message={item} onFeedback={onFeedback} />
        </View>
      )}
    />
  );
}
