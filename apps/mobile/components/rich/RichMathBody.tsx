import { useMemo } from "react";
import {
  StyleSheet,
  Text,
  View,
  type StyleProp,
  type TextStyle,
  type ViewStyle,
} from "react-native";

import { InlineCode } from "@/components/markdown/InlineCode";
import { inlineCodeTextStyle } from "@/components/markdown/markdownContentStyles";
import { MathText } from "@/components/rich/MathText";
import { MathBlock } from "@/components/rich/MathView";
import { RichBodyText } from "@/components/rich/RichBodyText";
import { isHeavyInlineMath } from "@/lib/math/fenceRetag";
import { readableLatexFallback } from "@/lib/math/text";
import { parseRichMathText } from "@/lib/markdown/richMathText";
import { useTheme } from "@/lib/theme";
import { Italic, Weight } from "@/lib/type";

/** Whether a rich-card string holds `$…$` maths that only RichMathBody can draw. */
export function hasRichMath(content: string): boolean {
  return parseRichMathText(content).some((part) => part.type === "math");
}

/** Style keys that place the text in its parent. With maths the words are
 * items in a wrapping row, so these belong on the row, not on every word. */
const LAYOUT_KEYS = [
  "flex", "flexGrow", "flexShrink", "flexBasis", "alignSelf", "width", "minWidth", "maxWidth",
  "margin", "marginTop", "marginBottom", "marginLeft", "marginRight", "marginHorizontal",
  "marginVertical", "marginStart", "marginEnd",
] as const;

function splitLayout(style: StyleProp<TextStyle>): { row: ViewStyle; text: TextStyle } {
  const text: Record<string, unknown> = { ...StyleSheet.flatten(style) };
  const row: Record<string, unknown> = {};
  for (const key of LAYOUT_KEYS) {
    if (key in text) {
      row[key] = text[key];
      delete text[key];
    }
  }
  return { row: row as ViewStyle, text: text as TextStyle };
}

/**
 * Math-aware rich-card text (callouts, steps, quiz cards) without invoking
 * MarkdownContent or rich-fence routing. Bold, italic and `code` work as in
 * RichBodyText; `$…$` is drawn as maths, never shown as source.
 */
export function RichMathBody({
  content,
  style,
  textColor,
  codeStyle,
  selectable = true,
}: {
  content: string;
  style?: StyleProp<TextStyle>;
  textColor?: string;
  /** The `code` pill's look; the reply's inline-code pill by default. */
  codeStyle?: StyleProp<TextStyle>;
  /** Off where the text sits inside a control (a quiz option) that takes the tap. */
  selectable?: boolean;
}) {
  const theme = useTheme();
  const parts = useMemo(() => parseRichMathText(content), [content]);
  const { row, text } = useMemo(() => splitLayout(style), [style]);
  // One VoiceOver element for the line, its maths read as words, not one stop per word.
  const label = useMemo(
    () =>
      parts
        .map((part) => (part.type === "math" ? ` ${readableLatexFallback(part.value)} ` : part.value))
        .join("")
        .replace(/\s+/g, " ")
        .trim(),
    [parts],
  );
  if (!parts.some((part) => part.type === "math")) {
    return <RichBodyText style={style} selectable={selectable}>{content}</RichBodyText>;
  }
  const mathColor = textColor ?? (typeof text.color === "string" ? text.color : theme.text);
  return (
    <View
      style={[styles.row, row]}
      testID="rich-math-body"
      accessible
      accessibilityRole="text"
      accessibilityLabel={label}
    >
      {parts.flatMap((part, index) => {
        if (part.type === "math") {
          return [isHeavyInlineMath(part.value)
            ? <MathBlock key={index} latex={part.value} />
            : <MathText key={index} latex={part.value} textColor={mathColor} />];
        }
        if (part.type === "code") {
          // One pill for the whole span, not a pill per word.
          return [
            <InlineCode key={index} style={[text, codeStyle ?? inlineCodeTextStyle(theme)]}>
              {part.value}
            </InlineCode>,
          ];
        }
        // Separate words can wrap around a sized fraction/radical. Never nest
        // those Views inside Text (iOS gives them a zero-sized attachment).
        return part.value.split(/(\n|[^\S\n]+)/).filter(Boolean).map((word, wordIndex) =>
          word === "\n" ? <View key={`${index}-${wordIndex}`} style={styles.break} /> : (
            <Text key={`${index}-${wordIndex}`} selectable={selectable} style={[
              text,
              part.bold && styles.bold,
              part.italic && styles.italic,
            ]}>{word}</Text>
          ),
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", flexShrink: 1 },
  break: { width: "100%", height: 0 },
  bold: { ...Weight.bold },
  italic: { ...Italic.regular },
});
