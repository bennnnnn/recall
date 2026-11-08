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
import {
  AccessibleElementChildren,
  useInsideAccessibleElement,
} from "@/components/rich/accessibleElement";
import { inlineCodeTextStyle } from "@/components/markdown/markdownContentStyles";
import { MathText } from "@/components/rich/MathText";
import { MathBlock } from "@/components/rich/MathView";
import { RichBodyText } from "@/components/rich/RichBodyText";
import { isHeavyInlineMath } from "@/lib/math/fenceRetag";
import { spokenFormula } from "@/lib/math/text";
import { parseRichMathText } from "@/lib/markdown/richMathText";
import { useTheme } from "@/lib/theme";
import { Italic, Weight } from "@/lib/type";

/** Whether a rich-card string holds `$…$` maths that only RichMathBody can draw. */
export function hasRichMath(content: string): boolean {
  return parseRichMathText(content).some((part) => part.type === "math");
}

/**
 * What a screen reader says for rich-card text: its words, with each `$…$`
 * read as words ("x squared"), never the source. An accessible parent that
 * holds a RichMathBody or ChipText (a quiz option) labels itself with this.
 */
export function richTextLabel(content: string): string {
  return parseRichMathText(content)
    .map((part) => (part.type === "math" ? ` ${spokenFormula(part.value)} ` : part.value))
    .join("")
    .replace(/\s+/g, " ")
    .trim();
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
  // Standalone (a step, a callout) the line is one screen-reader element, its
  // maths read as words, not one stop per word. Under an accessible parent the
  // parent is that element (see accessibleElement.tsx).
  const inside = useInsideAccessibleElement();
  const label = useMemo(() => (inside ? undefined : richTextLabel(content)), [inside, content]);
  if (!parts.some((part) => part.type === "math")) {
    return <RichBodyText style={style} selectable={selectable}>{content}</RichBodyText>;
  }
  const mathColor = textColor ?? (typeof text.color === "string" ? text.color : theme.text);
  // Maths the size of the words beside it: a follow-up's 15 pt line drew its maths at 16.
  const mathSize = typeof text.fontSize === "number" ? text.fontSize : undefined;
  return (
    <View
      style={[styles.row, row]}
      testID="rich-math-body"
      accessible={!inside}
      accessibilityRole={inside ? undefined : "text"}
      accessibilityLabel={label}
    >
      <AccessibleElementChildren>
        {parts.flatMap((part, index) => {
          if (part.type === "math") {
            return [isHeavyInlineMath(part.value)
              ? <MathBlock key={index} latex={part.value} />
              : <MathText key={index} latex={part.value} textColor={mathColor} fontSize={mathSize} />];
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
      </AccessibleElementChildren>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", flexShrink: 1 },
  break: { width: "100%", height: 0 },
  bold: { ...Weight.bold },
  italic: { ...Italic.regular },
});
