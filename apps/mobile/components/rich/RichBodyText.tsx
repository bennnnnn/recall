import { useMemo } from "react";
import { Text, type TextProps } from "react-native";

import { CODE_FONT } from "@/lib/fonts";
import { parseInlineMarkdown } from "@/lib/inlineMarkdown";
import { useTheme } from "@/lib/theme";

/**
 * Renders a rich-fence body string with minimal inline markdown (bold, italic,
 * inline code) without invoking the full MarkdownContent pipeline (avoids
 * heavy re-processing and recursive rich-fence routing inside a fence body).
 */
export function RichBodyText(props: TextProps) {
  const { children, style, ...rest } = props;
  const theme = useTheme();
  const text = typeof children === "string" ? children : "";
  const tokens = useMemo(() => parseInlineMarkdown(text), [text]);

  if (tokens.length === 0) {
    return (
      <Text style={style} {...rest}>
        {text}
      </Text>
    );
  }

  return (
    <Text style={style} {...rest}>
      {tokens.map((token, i) => {
        if (token.type === "bold") {
          return (
            <Text key={i} style={{ fontWeight: "800" }}>
              {token.value}
            </Text>
          );
        }
        if (token.type === "italic") {
          return (
            <Text key={i} style={{ fontStyle: "italic" }}>
              {token.value}
            </Text>
          );
        }
        if (token.type === "code") {
          return (
            <Text
              key={i}
              style={{
                fontFamily: CODE_FONT,
                fontSize: 13,
                color: theme.text,
                backgroundColor: theme.surfaceAlt,
                paddingHorizontal: 4,
                borderRadius: 4,
                overflow: "hidden",
              }}
            >
              {token.value}
            </Text>
          );
        }
        return <Text key={i}>{token.value}</Text>;
      })}
    </Text>
  );
}
