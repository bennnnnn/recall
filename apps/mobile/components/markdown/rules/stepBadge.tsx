import { Text, View } from "react-native";

import { STEP_BADGE } from "@/components/markdown/markdownContentStyles";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import type { Theme } from "@/lib/theme";
import { DYNAMIC_TYPE_MAX, Type, Weight } from "@/lib/type";

/**
 * A step's number in a grey pill: the server's "**1. Subtract 4 …**" and a model's
 * "### 1. Divide every term by a" draw it alike (November 2026). It sits on the label's
 * first line (`lineHeight`, the label's), so a label that wraps keeps its number on top.
 */
export function StepBadge({ n, t, lineHeight }: { n: string; t: Theme; lineHeight?: number }) {
  return (
    <View
      testID="step-badge"
      style={{
        marginTop: lineHeight ? Math.max(0, (lineHeight - STEP_BADGE.size) / 2) : 0,
        // A pill once large text makes the number wider than 22pt.
        minWidth: STEP_BADGE.size,
        minHeight: STEP_BADGE.size,
        paddingHorizontal: Space.xxs,
        borderRadius: Radius.full,
        backgroundColor: t.surfaceAlt,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Text
        style={{ ...Type.caption, ...Weight.bold, color: t.text }}
        maxFontSizeMultiplier={DYNAMIC_TYPE_MAX}
      >
        {n}
      </Text>
    </View>
  );
}
