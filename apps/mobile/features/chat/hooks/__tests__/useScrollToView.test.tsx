import { renderHook, waitFor } from "@testing-library/react-native";
import { AccessibilityInfo, type View } from "react-native";

import { useScrollToView } from "@/features/chat/hooks/useScrollToView";
import { Space } from "@/lib/space";

function thread() {
  const content = { content: true };
  const scrollToOffset = jest.fn();
  const listRef = {
    current: { getNativeScrollRef: () => ({ getInnerViewRef: () => content }), scrollToOffset },
  } as never;
  return { content, scrollToOffset, listRef };
}

/** A card 900pt down the thread's content. */
function card(content: object) {
  return {
    measureLayout: (relative: object, ok: (x: number, y: number) => void) => {
      if (relative === content) ok(0, 900);
    },
  } as unknown as View;
}

describe("scrolling the thread to a view inside a message", () => {
  afterEach(() => jest.restoreAllMocks());

  it("puts the view just under the header, gliding there", async () => {
    jest.spyOn(AccessibilityInfo, "isReduceMotionEnabled").mockResolvedValue(false);
    const { content, scrollToOffset, listRef } = thread();
    const { result } = await renderHook(() => useScrollToView(listRef, 100));
    result.current(card(content));
    expect(scrollToOffset).toHaveBeenCalledWith({ offset: 900 - 100 - Space.md, animated: true });
  });

  it("jumps there under Reduce Motion", async () => {
    jest.spyOn(AccessibilityInfo, "isReduceMotionEnabled").mockResolvedValue(true);
    const { content, scrollToOffset, listRef } = thread();
    const { result } = await renderHook(() => useScrollToView(listRef, 100));
    await waitFor(() => {
      result.current(card(content));
      expect(scrollToOffset).toHaveBeenLastCalledWith({ offset: 900 - 100 - Space.md, animated: false });
    });
  });
});
