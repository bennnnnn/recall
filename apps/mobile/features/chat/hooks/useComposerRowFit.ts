import { useState } from "react";
import type { LayoutChangeEvent } from "react-native";

import { COMPOSER_CONTROL_SIZE, composerSoftWrapLineCount } from "@/features/chat/model/composerLogic";
import { Space } from "@/lib/space";

function widthSetter(set: (update: (current: number) => number) => void) {
  return (event: LayoutChangeEvent) => {
    const next = Math.round(event.nativeEvent.layout.width);
    if (next > 0) set((current) => (current === next ? current : next));
  };
}

/**
 * Whether the draft still fits on one line beside the buttons. While it does, the composer
 * is one row: +, the field, then mic and live talk (or send). Once it wraps, the text takes
 * the card's full width and the buttons drop to a row under it, as they do in the full-height
 * editor. The fit is judged at the one-row field width (the card's row less + and the
 * trailing buttons), so the wider stacked field never flips the layout back.
 */
export function useComposerRowFit(input: string, fontScale: number) {
  const [rowWidth, setRowWidth] = useState(0);
  const [trailingWidth, setTrailingWidth] = useState(0);
  const inlineWidth = rowWidth - COMPOSER_CONTROL_SIZE - trailingWidth - 2 * Space.xxs;
  const wraps =
    Boolean(input) &&
    rowWidth > 0 &&
    trailingWidth > 0 &&
    composerSoftWrapLineCount(input, inlineWidth, fontScale) > 1;
  return {
    wraps,
    onRowLayout: widthSetter(setRowWidth),
    onTrailingLayout: widthSetter(setTrailingWidth),
  };
}
