import { useCallback } from "react";

import { useImageGeneration } from "@/features/images/hooks/useImageGeneration";
import { uploadSendAttachment } from "@/features/chat/hooks/useSendAttachment";
import { refusalCode, resolveChatError } from "@/features/chat/model/errorMessage";

type Options = Omit<Parameters<typeof useImageGeneration>[0], "uploadReference" | "failureMessage"> & {
  isPaid: boolean;
};

/** Image generation on the chat screen: the chat uploads its reference photo and words its failures. */
export function useChatImageGeneration({ isPaid, t, ...options }: Options) {
  const failureMessage = useCallback(
    // Every daily_limit from the picture endpoint is the picture's own cap.
    (message: string, code: string | undefined) =>
      resolveChatError({ message, code: refusalCode(code, "image_generation"), isPaid, t }).message,
    [isPaid, t],
  );
  return useImageGeneration({ ...options, t, uploadReference: uploadSendAttachment, failureMessage });
}
