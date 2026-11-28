import { useEffect } from "react";
import { useTranslation } from "react-i18next";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { subscribeChatGone } from "@/features/chat/model/chatGone";

/** Mounted once in the root layout: says a chat found gone was deleted elsewhere, once. */
export function ChatGoneNotice() {
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  useEffect(
    () => subscribeChatGone(() => feedback?.info(t("chat.gone_toast"), { icon: "trash" })),
    [feedback, t],
  );
  return null;
}
