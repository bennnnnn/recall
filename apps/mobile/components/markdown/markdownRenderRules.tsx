import {
  makeMdImg,
  makeMdMath,
  makeMdStyles,
  makeMdTable,
  type MdImgStyles,
  type MdMathStyles,
  type MdTableStyles,
} from "@/components/markdown/markdownContentStyles";
import { fenceRule } from "@/components/markdown/markdownFenceRender";
import { blockRules } from "@/components/markdown/rules/blocks";
import { codeRules } from "@/components/markdown/rules/code";
import { inlineRules } from "@/components/markdown/rules/inline";
import { linkRules } from "@/components/markdown/rules/links";
import { listRules } from "@/components/markdown/rules/lists";
import { tableRules } from "@/components/markdown/rules/tables";
import { textRules } from "@/components/markdown/rules/textWithMath";
import { withStableNodeKeys } from "@/components/markdown/stableNodeKeys";
import { renderRules as libraryRules, type RenderRules } from "react-native-markdown-display";

import type { Theme } from "@/lib/theme";

function makeSharedRules(
  t: Theme,
  mdTable: MdTableStyles,
  mdMath: MdMathStyles,
  mdImg: MdImgStyles,
  mdCodeInline: object,
) {
  return {
    ...linkRules(mdImg),
    ...textRules(t, mdTable, mdMath),
    ...inlineRules(mdTable, mdMath),
    ...listRules(t, mdMath),
    ...blockRules(t, mdTable, mdMath),
    ...codeRules(mdTable, mdCodeInline),
    ...tableRules(),
  };
}

/**
 * `rules` draw a reply; `continuedRules` draw a piece of a reply whose last
 * list goes on in the next piece (`listRules`). The same rules draw a reply
 * while it streams and once it settles: what differs reads `ReplyStreaming`.
 */
export function makeRenderRules(t: Theme) {
  const mdMath = makeMdMath(t);
  const mdTable = makeMdTable(t);
  const mdImg = makeMdImg(t);
  const mdStyles = makeMdStyles(t);
  const shared = {
    ...libraryRules,
    ...makeSharedRules(t, mdTable, mdMath, mdImg, mdStyles.code_inline),
    fence: fenceRule,
    code_block: fenceRule,
  };
  const rules: RenderRules = withStableNodeKeys(shared);
  const continuedRules: RenderRules = withStableNodeKeys({
    ...shared,
    ...listRules(t, mdMath, true),
  });
  return { rules, continuedRules, mdStyles };
}
