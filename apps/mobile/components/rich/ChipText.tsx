import { type ComponentProps, useMemo } from "react";
import { Text } from "react-native";

import { parseInlineMarkdown } from "@/lib/markdown/inlineMarkdown";
import { Italic, Weight } from "@/lib/type";

type TextStyleProp = ComponentProps<typeof Text>["style"];

/** Inline markdown with `code` drawn as a gray chip, as in ChatGPT's lesson cards. */
export function ChipText({
  children,
  style,
  chip,
}: {
  children: string;
  style: TextStyleProp;
  chip: TextStyleProp;
}) {
  return (
    <Text style={style}>
      <ChipSpans text={children} chip={chip} />
    </Text>
  );
}

export function ChipSpans({ text, chip }: { text: string; chip: TextStyleProp }) {
  const tokens = useMemo(() => parseInlineMarkdown(text), [text]);
  if (tokens.length === 0) return <>{text}</>;
  return (
    <>
      {tokens.map((token, index) => {
        if (token.type === "code") {
          // Thin spaces pad the chip; nested Text takes no padding.
          return (
            <Text key={index} style={chip}>
              {` ${token.value} `}
            </Text>
          );
        }
        if (token.type === "bold") {
          return (
            <Text key={index} style={Weight.bold}>
              {token.value}
            </Text>
          );
        }
        if (token.type === "italic") {
          return (
            <Text key={index} style={Italic.regular}>
              {token.value}
            </Text>
          );
        }
        return token.value;
      })}
    </>
  );
}
