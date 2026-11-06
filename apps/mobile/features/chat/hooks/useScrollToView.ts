import { useCallback, type RefObject } from "react";
import type { HostInstance, ScrollViewInstance } from "react-native";
import type { FlashListRef } from "@shopify/flash-list";

import type { ScrollToView } from "@/components/rich/answerJump";
import type { Message } from "@/lib/api";
import { useReduceMotion } from "@/lib/reduceMotion";
import { Space } from "@/lib/space";

/** Room left between the header and a view the thread scrolls to. */
const TOP_GAP = Space.md;

/**
 * Scrolls the thread so a view inside a message (an answer card) sits just under the
 * header: measured against the list's scroll content, so the offset is the view's own
 * place in the thread wherever its message is. A jump, not a glide, under Reduce Motion.
 */
export function useScrollToView(
  listRef: RefObject<FlashListRef<Message> | null>,
  topInset: number,
): ScrollToView {
  const reduceMotion = useReduceMotion();
  return useCallback(
    (target: HostInstance) => {
      const list = listRef.current;
      const scroller = list?.getNativeScrollRef() as ScrollViewInstance | null | undefined;
      const content = scroller?.getInnerViewRef();
      if (!list || !content) return;
      target.measureLayout(
        content,
        (_x, y) => list.scrollToOffset({ offset: Math.max(0, y - topInset - TOP_GAP), animated: !reduceMotion }),
        () => {},
      );
    },
    [listRef, topInset, reduceMotion],
  );
}
