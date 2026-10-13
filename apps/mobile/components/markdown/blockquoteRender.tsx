import { Children, type ReactNode } from "react";
import { View } from "react-native";

import {
  blockquoteCitation,
  type AstNode,
} from "@/components/markdown/markdownAstHelpers";
import { QuoteBlock } from "@/components/rich/QuoteBlock";
import { PARAGRAPH_GAP, TRIM_TRAILING_GAP } from "@/components/markdown/markdownContentStyles";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

// Ordinary indented prose (a citation is the quote card): the block rhythm and
// a neutral rule, so the indent reads as a quote at a glance.
const indentedProse = {
  marginTop: 0,
  marginBottom: PARAGRAPH_GAP,
  paddingLeft: Space.sm,
  borderLeftWidth: 2,
};

/** Quote card for a citation; every other blockquote is indented prose. */
export function renderBlockquote(node: AstNode, children: ReactNode): ReactNode {
  const citation = blockquoteCitation(node);
  if (citation) {
    return (
      <QuoteBlock
        key={node.key}
        author={citation.author ?? undefined}
        testID="quote-card"
      >
        {Children.toArray(children).slice(0, citation.bodyCount)}
      </QuoteBlock>
    );
  }
  return (
    <IndentedProse key={node.key}>{children}</IndentedProse>
  );
}

function IndentedProse({ children }: { children: ReactNode }) {
  const t = useTheme();
  return (
    <View testID="indented-prose" style={[indentedProse, { borderLeftColor: t.border }]}>
      <View style={TRIM_TRAILING_GAP}>{children}</View>
    </View>
  );
}
