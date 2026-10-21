import { act, renderHook } from "@testing-library/react-native";
import type { NativeScrollEvent, NativeSyntheticEvent } from "react-native";

import { useChatScroll } from "@/features/chat/hooks/useChatScroll";

jest.mock("@/lib/haptics", () => ({ tap: jest.fn() }));

/** A FlashList that reports `rows` of content in a `window`, scrolled to `offset`. */
function fakeList(rows: number) {
  const state = { rows, window: 600, offset: 0 };
  const scroller = { scrollToEnd: jest.fn() };
  const list = {
    getAbsoluteLastScrollOffset: () => state.offset,
    getChildContainerDimensions: () => ({ width: 390, height: state.rows }),
    getWindowSize: () => ({ width: 390, height: state.window }),
    getNativeScrollRef: () => scroller,
    scrollToEnd: jest.fn(),
    scrollToOffset: jest.fn(),
  };
  return { state, scroller, list };
}

function scrollEvent(offset: number, content: number, viewport = 600) {
  return {
    nativeEvent: {
      contentOffset: { x: 0, y: offset },
      contentSize: { width: 390, height: content },
      layoutMeasurement: { width: 390, height: viewport },
    },
  } as NativeSyntheticEvent<NativeScrollEvent>;
}

type Props = { chatId: string | null; messagesLength: number; streamActive: boolean };

async function mountScroll(fake: ReturnType<typeof fakeList>, initial: Props) {
  const hook = await renderHook((props: Props) => useChatScroll({ ...props, windowHeight: 800, keyboardHeight: 0 }), {
    initialProps: initial,
  });
  (hook.result.current.listRef as { current: unknown }).current = fake.list;
  return hook;
}

beforeEach(() => jest.useFakeTimers());
afterEach(() => jest.useRealTimers());

describe("useChatScroll pins to the bottom from layout", () => {
  const props: Props = { chatId: "chat-a", messagesLength: 4, streamActive: true };

  it("follows rows that grew, in the commit that measured them", async () => {
    const fake = fakeList(1000);
    const { result } = await mountScroll(fake, props);
    await act(async () => {
      result.current.listScroll.onLayoutCommit();
    });
    fake.scroller.scrollToEnd.mockClear();

    fake.state.rows = 1060;
    await act(async () => {
      result.current.listScroll.onLayoutCommit();
    });
    expect(fake.scroller.scrollToEnd).toHaveBeenCalledWith({ animated: false });
    // FlashList's own scrollToEnd waits a tick: the native scroller is used instead.
    expect(fake.list.scrollToEnd).not.toHaveBeenCalled();

    // A commit with nothing new does not scroll again.
    fake.scroller.scrollToEnd.mockClear();
    await act(async () => {
      result.current.listScroll.onLayoutCommit();
    });
    expect(fake.scroller.scrollToEnd).not.toHaveBeenCalled();
  });

  it("does not pull the list while the reader drags it, and follows again after", async () => {
    const fake = fakeList(1000);
    const { result } = await mountScroll(fake, props);
    await act(async () => {
      result.current.listScroll.onLayoutCommit();
    });
    fake.scroller.scrollToEnd.mockClear();

    await act(async () => {
      result.current.listScroll.onReaderScrollBegin();
    });
    fake.state.rows = 1100;
    await act(async () => {
      result.current.listScroll.onLayoutCommit();
    });
    expect(fake.scroller.scrollToEnd).not.toHaveBeenCalled();

    fake.state.offset = 500;
    await act(async () => {
      result.current.handleScrollEnd();
    });
    fake.state.rows = 1150;
    await act(async () => {
      result.current.listScroll.onLayoutCommit();
    });
    expect(fake.scroller.scrollToEnd).toHaveBeenCalledTimes(1);
  });

  it("stays put once the reader scrolled away from the bottom", async () => {
    const fake = fakeList(3000);
    const { result } = await mountScroll(fake, props);
    await act(async () => {
      result.current.handleScroll(scrollEvent(200, 3000));
    });
    fake.state.rows = 3200;
    await act(async () => {
      result.current.listScroll.onLayoutCommit();
    });
    expect(fake.scroller.scrollToEnd).not.toHaveBeenCalled();
  });

  it("follows the scroll content too (a settling reply's padding and chrome)", async () => {
    const fake = fakeList(1000);
    const { result } = await mountScroll(fake, props);
    await act(async () => {
      result.current.listScroll.onContentSizeChange(390, 1300);
    });
    fake.scroller.scrollToEnd.mockClear();
    await act(async () => {
      result.current.listScroll.onContentSizeChange(390, 1340);
    });
    expect(fake.scroller.scrollToEnd).toHaveBeenCalledWith({ animated: false });
  });

  it("leaves a thread that fits the screen alone", async () => {
    const fake = fakeList(300);
    const { result } = await mountScroll(fake, props);
    fake.state.rows = 360;
    await act(async () => {
      result.current.listScroll.onLayoutCommit();
    });
    expect(fake.scroller.scrollToEnd).not.toHaveBeenCalled();
  });
});

describe("useChatScroll opens a chat at its end", () => {
  const closed: Props = { chatId: null, messagesLength: 0, streamActive: false };

  it("draws an opened chat once a commit finds it at its end", async () => {
    const fake = fakeList(2000);
    const { result, rerender } = await mountScroll(fake, closed);
    await rerender({ chatId: "chat-b", messagesLength: 12, streamActive: false });
    expect(result.current.listScroll.hidden).toBe(true);

    await act(async () => {
      result.current.listScroll.onLayoutCommit();
    });
    expect(fake.scroller.scrollToEnd).toHaveBeenCalledWith({ animated: false });
    expect(result.current.listScroll.hidden).toBe(true);

    fake.state.offset = 1400;
    await act(async () => {
      result.current.listScroll.onLayoutCommit();
    });
    expect(result.current.listScroll.hidden).toBe(false);
  });

  it("draws an opened chat that fits the screen at once", async () => {
    const fake = fakeList(400);
    const { result, rerender } = await mountScroll(fake, closed);
    await rerender({ chatId: "chat-b", messagesLength: 2, streamActive: false });
    expect(result.current.listScroll.hidden).toBe(true);
    await act(async () => {
      result.current.listScroll.onLayoutCommit();
    });
    expect(result.current.listScroll.hidden).toBe(false);
    expect(fake.scroller.scrollToEnd).not.toHaveBeenCalled();
  });

  it("draws it after a short wait if the list never reports its end", async () => {
    const fake = fakeList(2000);
    const { result, rerender } = await mountScroll(fake, closed);
    await rerender({ chatId: "chat-b", messagesLength: 12, streamActive: false });
    expect(result.current.listScroll.hidden).toBe(true);
    await act(async () => {
      jest.advanceTimersByTime(300);
    });
    expect(result.current.listScroll.hidden).toBe(false);
  });

  it("never hides a new chat taking its id under its first message", async () => {
    const fake = fakeList(200);
    const { result, rerender } = await mountScroll(fake, { chatId: null, messagesLength: 1, streamActive: false });
    await rerender({ chatId: "chat-c", messagesLength: 1, streamActive: false });
    expect(result.current.listScroll.hidden).toBe(false);
  });
});

describe("useChatScroll leaves a highlighted search hit to its own scroll", () => {
  it("does not put a chat opened for a hit at its end, nor pull it there as rows grow", async () => {
    const fake = fakeList(2000);
    const { result, rerender } = await mountScroll(fake, { chatId: null, messagesLength: 0, streamActive: false });
    await act(async () => {
      result.current.holdForHighlight(true);
    });
    await rerender({ chatId: "chat-b", messagesLength: 12, streamActive: false });
    expect(result.current.listScroll.hidden).toBe(false);

    await act(async () => {
      result.current.listScroll.onLayoutCommit();
      result.current.listScroll.onListLayout(600);
      result.current.listScroll.onContentSizeChange(390, 2000);
    });
    fake.state.rows = 2100;
    await act(async () => {
      result.current.listScroll.onLayoutCommit();
      result.current.listScroll.onContentSizeChange(390, 2100);
    });
    expect(fake.scroller.scrollToEnd).not.toHaveBeenCalled();

    // The highlight over, growth at the bottom is followed again.
    await act(async () => {
      result.current.holdForHighlight(false);
    });
    fake.state.rows = 2200;
    await act(async () => {
      result.current.listScroll.onLayoutCommit();
    });
    expect(fake.scroller.scrollToEnd).toHaveBeenCalledWith({ animated: false });
  });

  it("draws a chat already opening where it is once its hit is known", async () => {
    const fake = fakeList(2000);
    const { result, rerender } = await mountScroll(fake, { chatId: null, messagesLength: 0, streamActive: false });
    await rerender({ chatId: "chat-b", messagesLength: 12, streamActive: false });
    expect(result.current.listScroll.hidden).toBe(true);

    await act(async () => {
      result.current.holdForHighlight(true);
    });
    expect(result.current.listScroll.hidden).toBe(false);
    await act(async () => {
      result.current.listScroll.onLayoutCommit();
    });
    expect(fake.scroller.scrollToEnd).not.toHaveBeenCalled();
  });
});
