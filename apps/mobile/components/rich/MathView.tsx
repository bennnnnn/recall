import { useMemo } from "react";
import { StyleSheet, Text, useWindowDimensions, View } from "react-native";
import RenderHtml from "react-native-render-html";
import katex from "katex";

import { C } from "@/constants/Colors";

type Props = { latex: string; displayMode?: boolean };

function renderKatex(latex: string, displayMode: boolean): string {
  try {
    return katex.renderToString(latex, {
      throwOnError: false,
      displayMode,
      output: "html",
    });
  } catch {
    return `<code>${latex}</code>`;
  }
}

export function MathInline({ latex }: { latex: string }) {
  const { width } = useWindowDimensions();
  const html = useMemo(() => renderKatex(latex, false), [latex]);
  return (
    <View style={s.inlineWrap}>
      <RenderHtml contentWidth={width} source={{ html }} baseStyle={s.base} />
    </View>
  );
}

export function MathBlock({ latex }: Props) {
  const { width } = useWindowDimensions();
  const html = useMemo(() => renderKatex(latex, true), [latex]);
  return (
    <View style={s.blockWrap}>
      <RenderHtml
        contentWidth={width - 64}
        source={{ html }}
        baseStyle={s.base}
      />
    </View>
  );
}

const s = StyleSheet.create({
  inlineWrap: {
    paddingHorizontal: 4,
    paddingVertical: 1,
    borderRadius: 4,
    backgroundColor: C.contentSurface,
    marginHorizontal: 2,
  },
  blockWrap: {
    alignSelf: "stretch",
    backgroundColor: C.contentSurface,
    borderRadius: 10,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.border,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginVertical: 8,
  },
  base: { color: C.text, fontSize: 16, lineHeight: 22 },
});
