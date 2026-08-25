import { useMemo } from "react";

import { computeChatLayoutMetrics } from "@/lib/chatComposerLogic";

type Options = {
  insetsTop: number;
  insetsBottom: number;
  windowHeight: number;
  keyboardHeight: number;
  composerHeight: number;
  attachmentExtra: number;
  mathBarExtra?: number;
  messagesLength: number;
  streaming: boolean;
  lastMessageId?: string;
};

export function useChatLayoutMetrics(options: Options) {
  return useMemo(
    () => computeChatLayoutMetrics(options),
    [
      options.insetsTop,
      options.insetsBottom,
      options.windowHeight,
      options.keyboardHeight,
      options.composerHeight,
      options.attachmentExtra,
      options.mathBarExtra,
      options.messagesLength,
      options.streaming,
      options.lastMessageId,
    ],
  );
}
