import { useEffect } from "react";
import { useTranslation } from "react-i18next";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { subscribeChatGone } from "@/features/chat/model/chatGone";

/** Mounted once in the root layout: says once that a chat found gone no longer exists (deleted on
 * another device, or a draft chat the server let go: it names no device). */
export function ChatGoneNotice() {
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  useEffect(
    () => subscribeChatGone(() => feedback?.info(t("chat.gone_toast"), { icon: "trash" })),
    [feedback, t],
  );
  return null;
}
