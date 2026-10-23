import { useCallback } from "react";

import { useImageGeneration } from "@/features/images/hooks/useImageGeneration";
import { uploadSendAttachment } from "@/features/chat/hooks/useSendAttachment";
import { refusalCode, resolveChatError } from "@/features/chat/model/errorMessage";

type Options = Omit<Parameters<typeof useImageGeneration>[0], "uploadReference" | "describeFailure"> & {
  isPaid: boolean;
};

/** Image generation on the chat screen: the chat uploads its reference photo and words its failures. */
export function useChatImageGeneration({ isPaid, t, ...options }: Options) {
  const describeFailure = useCallback(
    (message: string, code: string | undefined) => {
      // Every daily_limit from the picture endpoint is the picture's own cap.
      const resolved = resolveChatError({ message, code: refusalCode(code, "image_generation"), isPaid, t });
      // A spent allowance or a refused picture (the chat's quota and notice kinds) fails again.
      return { message: resolved.message, retryable: resolved.kind !== "quota" && resolved.kind !== "notice" };
    },
    [isPaid, t],
  );
  return useImageGeneration({ ...options, t, uploadReference: uploadSendAttachment, describeFailure });
}
