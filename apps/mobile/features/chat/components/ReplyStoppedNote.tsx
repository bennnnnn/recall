import { useMemo, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { useClarifyActions } from "@/components/rich/clarifyContext";
import type { Message } from "@/lib/api";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import { Button } from "@/ui/controls/Button";

type Props = {
  message: Message;
  /** The newest reply: only its Continue may still be sent. */
  latest?: boolean;
  /** The user message sent after this reply, if any: Continue, or something else. */
  after?: string | null;
};

/** The line under a reply that did not finish: which way it ended. */
function stoppedNoteKey(message: Message): string {
  if (message.replyNotSaved) return "chat.reply_not_saved";
  return message.completion === "interrupted" ? "chat.reply_cut_off" : "chat.generation_stopped";
}

/**
 * Under a reply that did not finish. One the server cut off (it ran out of room, or the
 * model failed partway) says so, and the newest one offers Continue: a user message sent
 * through the chat's own send path, as a clarify card's button sends its picks, which the
 * server reads as "go on from where it stopped". A reply the user stopped keeps its plain
 * line and no button. Nothing under a reply that finished.
 */
export function ReplyStoppedNote({ message, latest = false, after = null }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const actions = useClarifyActions();
  const [sent, setSent] = useState(false);
  if (!message.generationStopped && !message.completion && !message.replyNotSaved) return null;
  const offer =
    message.completion === "interrupted" && latest && after == null && actions != null && !sent;

  const continueReply = () => {
    if (!actions || actions.busy) return;
    setSent(true);
    // Refused before it went out (offline): the button stays to send again.
    void actions.send(t("chat.continue_reply")).then((went) => {
      if (!went) setSent(false);
    });
  };

  return (
    <View style={s.wrap}>
      <Text style={s.note}>{t(stoppedNoteKey(message))}</Text>
      {offer ? (
        <Button
          title={t("chat.continue_reply")}
          variant="outline"
          size="sm"
          icon="enter"
          onPress={continueReply}
          disabled={actions.busy}
          style={s.button}
          testID="reply-continue"
        />
      ) : null}
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: { marginTop: Space.xs, alignItems: "flex-start", gap: Space.xs },
    note: { ...Type.compact, color: t.textTertiary },
    button: { alignSelf: "flex-start" },
  });
}
