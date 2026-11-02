import { useRef } from "react";
import { StyleSheet, Text, View } from "react-native";

import { COMPOSER_INPUT_LINE_HEIGHT } from "@/features/chat/model/composerLogic";
import { DYNAMIC_TYPE_MAX, Type } from "@/lib/type";

export type ComposerTextSize = { height: number };

type Props = {
  text: string;
  /** The field's width; the draft wraps here exactly as the input does. */
  width: number;
  onMeasure: (size: ComposerTextSize) => void;
};

/**
 * Lays the draft out off screen in the field's font at the field width: how many
 * lines it really takes. Glyph estimates run wide, which grew the field before
 * the text wrapped.
 */
export function ComposerTextMeasure({ text, width, onMeasure }: Props) {
  const height = useRef(0);
  if (!text || width <= 0) return null;
  // A trailing return opens a line the input shows; Text drops it without a glyph after it.
  const shown = `${text}\u200b`;
  return (
    <View
      style={styles.box}
      pointerEvents="none"
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      <Text
        style={[styles.text, { width }]}
        maxFontSizeMultiplier={DYNAMIC_TYPE_MAX}
        onLayout={(e) => {
          const next = Math.ceil(e.nativeEvent.layout.height);
          if (next === height.current) return;
          height.current = next;
          onMeasure({ height: next });
        }}
      >
        {shown}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  // Absolute and see-through, so it takes no room.
  box: { position: "absolute", left: 0, top: 0, opacity: 0 },
  text: { ...Type.body, lineHeight: COMPOSER_INPUT_LINE_HEIGHT },
});
