import { Children, type ReactNode } from "react";
import { View } from "react-native";

import {
  blockquoteCitation,
  type AstNode,
} from "@/components/markdown/markdownAstHelpers";
import { QuoteBlock } from "@/components/rich/QuoteBlock";
import { Space } from "@/lib/space";

const indentedProse = {
  marginTop: Space.xs,
  marginBottom: Space.xs,
  paddingLeft: Space.sm,
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
    <View key={node.key} testID="indented-prose" style={indentedProse}>
      {children}
    </View>
  );
}
