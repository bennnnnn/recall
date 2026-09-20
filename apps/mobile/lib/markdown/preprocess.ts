import { retagMoleculeMathToSmiles } from "@/lib/chemistry/fence";
import {
  collapseAdjacentMoleculeFences,
  dropRedundantMolecule3dFences,
} from "@/lib/chemistry/moleculePair";
import { flattenIntegrationConnectNotes } from "@/lib/markdown/flattenIntegrationConnectNotes";
import {
  convertCalloutBlocks,
  promoteCalloutBlockquotes,
  promoteQuotedAttributions,
  splitBlockquoteInlineAttribution,
} from "@/lib/markdown/preprocessCallouts";
import {
  convertBlockMath,
  repairCorruptedPriceTierMarkdown,
  unwrapCorruptedMathFences,
} from "@/lib/markdown/preprocessMathBlocks";
import { layoutCheckVerificationLines } from "@/lib/markdown/preprocessMathChecks";
import {
  breakAttachedMathFences,
  closeInterruptedMathFences,
  dedentMisindentedMarkdownSteps,
  inlineShortMathFences,
  liftMathFencesOutOfLists,
  unwrapProseMathBackticks,
} from "@/lib/markdown/preprocessMathFences";
import {
  normalizeBoldInlineMath,
  protectMathEscapes,
  separateConsecutiveMathLines,
} from "@/lib/markdown/preprocessMathInline";
import {
  breakMidlineAtxHeadings,
  convertDetailsBlocks,
  mergeStrandedColons,
  retagVegaFences,
  stripBoldListLabelContinuationColons,
  wrapBareVegaJson,
} from "@/lib/markdown/preprocessNormalize";
import {
  normalizeMarkdownTables,
  unwrapNonCodeFences,
} from "@/lib/markdown/preprocessTables";
import { retagMathAndDiagramFences } from "@/lib/math/fenceRetag";
import { normalizeImplicitMath } from "@/lib/math/normalizeImplicit";
import { applyOutsideFences } from "@/lib/mdFenceScan";
import { repairBrokenMarkdownLinks } from "@/lib/placesList";

export { splitInlineMath } from "@/lib/markdown/inlineMath";
export {
  promoteCalloutBlockquotes,
  promoteQuotedAttributions,
  quotedAttributionToBlockquote,
  splitBlockquoteInlineAttribution,
} from "@/lib/markdown/preprocessCallouts";
export {
  breakAttachedMathFences,
  dedentMisindentedMarkdownSteps,
  inlineShortMathFences,
  liftMathFencesOutOfLists,
  unwrapProseMathBackticks,
} from "@/lib/markdown/preprocessMathFences";
export { layoutCheckVerificationLines } from "@/lib/markdown/preprocessMathChecks";
export { normalizeBoldInlineMath } from "@/lib/markdown/preprocessMathInline";
export {
  breakMidlineAtxHeadings,
  looksLikeMarkdownListProse,
  mergeStrandedColons,
  stripBoldListLabelContinuationColons,
} from "@/lib/markdown/preprocessNormalize";
export {
  isPipeTable,
  normalizeMarkdownTables,
} from "@/lib/markdown/preprocessTables";

export function preprocessMarkdown(
  content: string,
  mathFormat?: (expr: string) => string,
): string {
  let out = repairBrokenMarkdownLinks(content);
  // Do this before math normalization can reinterpret a punctuation-only
  // continuation line.
  out = stripBoldListLabelContinuationColons(out);
  out = repairCorruptedPriceTierMarkdown(out);
  out = normalizeImplicitMath(out, mathFormat);
  out = normalizeBoldInlineMath(out);
  // The model often wraps inline math in backticks (`` `$x^2 = 4$` ``), which
  // markdown renders as inline CODE → raw literal `$...$`. Un-wrap backtick-
  // wrapped `$...$` so it renders as math inline with the prose (in sync with
  // the text, no late fence pop-in).
  out = applyOutsideFences(out, (prose) => prose.replace(/`(\$[^`\n]+?\$)`/g, "$1"));

  out = flattenIntegrationConnectNotes(out);
  out = promoteCalloutBlockquotes(out);
  out = promoteQuotedAttributions(out);
  out = splitBlockquoteInlineAttribution(out);
  out = convertCalloutBlocks(out);
  out = flattenIntegrationConnectNotes(out);

  out = convertDetailsBlocks(out);

  out = convertBlockMath(out);
  out = breakAttachedMathFences(out);
  out = closeInterruptedMathFences(out);
  out = dedentMisindentedMarkdownSteps(out);
  out = unwrapCorruptedMathFences(out);

  out = normalizeMarkdownTables(out);

  // Re-tag Vega fences / bare JSON with linear scans (no nested [\s\S]*? ReDoS).
  out = retagVegaFences(out);
  out = wrapBareVegaJson(out);

  // Molecule formulas before math retag — otherwise bare `O=O` becomes ```math.
  out = retagMoleculeMathToSmiles(out);
  out = retagMathAndDiagramFences(out);

  out = unwrapNonCodeFences(out);

  out = protectMathEscapes(out);
  out = mergeStrandedColons(out);
  out = breakMidlineAtxHeadings(out);
  out = breakAttachedMathFences(out);
  out = closeInterruptedMathFences(out);
  out = dedentMisindentedMarkdownSteps(out);
  out = liftMathFencesOutOfLists(out);
  out = inlineShortMathFences(out);
  out = unwrapProseMathBackticks(out);
  out = separateConsecutiveMathLines(out);
  out = collapseAdjacentMoleculeFences(out);
  out = dropRedundantMolecule3dFences(out);
  // After fence inlining: a trailing ✓ used to abort the = split, and
  // inlineShortMathFences can glue `$...$` back onto `For x = 3:`.
  out = layoutCheckVerificationLines(out);
  return out;
}
