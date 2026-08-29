import { useCallback, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type { ClientGeo } from "@/lib/clientGeo";
import type { Message, User } from "@/lib/api";
import { isImageOnlyAssistantContent } from "@/lib/imageGenIntent";
import { resolveClientGeoForQuery } from "@/lib/resolveClientGeoForQuery";

type Params = {
  token: string | null;
  messages: Message[];
  user: User | null;
  updateUser: (patch: Partial<User>) => Promise<void>;
  regenerateResponse: (model?: string | null, clientGeo?: ClientGeo | null) => Promise<void>;
  /** Pop the last assistant + show typing immediately, before geo. */
  beginRegenerateUi?: () => void;
  /** Restore the prior assistant when geo is cancelled. */
  cancelRegenerateUi?: () => void;
  /**
   * Called when the last assistant message is an image-gen turn. Receives the
   * last user message content (the prompt) so the caller can re-run image
   * generation directly instead of the SSE stream.
   */
  regenerateImage?: (lastUserContent: string) => void;
};

export function useChatRegenerate({
  token,
  messages,
  updateUser,
  regenerateResponse,
  beginRegenerateUi,
  cancelRegenerateUi,
  regenerateImage,
}: Params) {
  const { t } = useTranslation();
  const [regenerating, setRegenerating] = useState(false);
  const inFlightRef = useRef(false);

  const regenerate = useCallback(
    async (model: string) => {
      if (!token || inFlightRef.current) return;
      const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
      // If the last assistant turn was an image-gen reply, route regenerate
      // through the image-gen path so the user sees the ImageGenPlaceholder
      // instead of a generic (and wrong) text stream.
      if (
        regenerateImage &&
        lastAssistant &&
        isImageOnlyAssistantContent(lastAssistant.content)
      ) {
        const lastUser = [...messages].reverse().find((m) => m.role === "user");
        regenerateImage(lastUser?.content ?? "");
        return;
      }
      inFlightRef.current = true;
      setRegenerating(true);
      beginRegenerateUi?.();
      try {
        const lastUser = [...messages].reverse().find((m) => m.role === "user");
        const result = await resolveClientGeoForQuery(
          token,
          lastUser?.content ?? "",
          t,
          updateUser,
        );
        if (!result.ok) {
          cancelRegenerateUi?.();
          return;
        }
        await regenerateResponse(model, result.clientGeo);
      } finally {
        inFlightRef.current = false;
        setRegenerating(false);
      }
    },
    [
      token,
      messages,
      regenerateResponse,
      beginRegenerateUi,
      cancelRegenerateUi,
      regenerateImage,
      t,
      updateUser,
    ],
  );

  return { regenerate, regenerating };
}
