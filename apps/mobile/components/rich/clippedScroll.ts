/** A sideways scroll whose content may be wider than it: what tells the reader there is more. */
import { useRef } from "react";
import type { LayoutChangeEvent, ScrollViewInstance } from "react-native";

/**
 * The scroll bar flashes once the content is known to overflow its scroll, so a cut edge
 * reads as more to see. Spread the result onto a horizontal ScrollView.
 */
export function useFlashWhenClipped() {
  const ref = useRef<ScrollViewInstance>(null);
  const seen = useRef({ viewport: 0, content: 0, flashed: false });
  const flashIfClipped = () => {
    const size = seen.current;
    if (size.flashed || size.viewport <= 0 || size.content <= size.viewport + 1) return;
    size.flashed = true;
    ref.current?.flashScrollIndicators();
  };
  return {
    ref,
    onLayout: (event: LayoutChangeEvent) => {
      seen.current.viewport = event.nativeEvent.layout.width;
      flashIfClipped();
    },
    onContentSizeChange: (width: number) => {
      seen.current.content = width;
      flashIfClipped();
    },
  };
}
