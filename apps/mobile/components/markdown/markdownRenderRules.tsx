import {
  makeMdImg,
  makeMdMath,
  makeMdStyles,
  makeMdTable,
  type MdImgStyles,
  type MdMathStyles,
  type MdTableStyles,
} from "@/components/markdown/markdownContentStyles";
import {
  renderSettledFence,
  renderStreamingFence,
} from "@/components/markdown/markdownFenceRender";
import { blockRules } from "@/components/markdown/rules/blocks";
import { codeRules } from "@/components/markdown/rules/code";
import { inlineRules } from "@/components/markdown/rules/inline";
import { linkRules } from "@/components/markdown/rules/links";
import { listRules } from "@/components/markdown/rules/lists";
import { tableRules } from "@/components/markdown/rules/tables";
import { textRules } from "@/components/markdown/rules/textWithMath";
import type { Theme } from "@/lib/theme";

function makeSharedRules(
  t: Theme,
  mdTable: MdTableStyles,
  mdMath: MdMathStyles,
  mdImg: MdImgStyles,
  mdCodeInline: object,
  streaming = false,
) {
  return {
    ...linkRules(mdImg),
    ...textRules(t, mdTable, mdMath),
    ...inlineRules(mdTable, mdMath),
    ...listRules(t, mdMath),
    ...blockRules(t, mdTable, mdMath, streaming),
    ...codeRules(mdTable, mdCodeInline),
    ...tableRules(),
  };
}

export function makeRenderRules(t: Theme, streaming = false) {
  const mdMath = makeMdMath(t);
  const mdTable = makeMdTable(t);
  const mdImg = makeMdImg(t);
  const mdStyles = makeMdStyles(t);
  // A streaming reply is not yet the server's final text: no answer check in it.
  const fence = streaming ? renderStreamingFence : renderSettledFence;
  const rules = {
    ...makeSharedRules(t, mdTable, mdMath, mdImg, mdStyles.code_inline, streaming),
    fence,
    code_block: fence,
  };
  return { rules, mdStyles };
}
