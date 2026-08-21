import { ReactNode } from "react";

import i18n from "@/lib/i18n";

import { PlacesListBlock } from "@/components/PlacesListBlock";
import { CalloutBlock } from "@/components/rich/CalloutBlock";
import { parsePlacesJson } from "@/lib/placesList";
import { AnswerBlock } from "@/components/rich/AnswerBlock";
import { CollapsibleBlock } from "@/components/rich/CollapsibleBlock";
import { ComparisonBlock } from "@/components/rich/ComparisonBlock";
import { CircularClockBlock } from "@/components/rich/CircularClockBlock";
import { EmailCard } from "@/components/rich/EmailCard";
import { KeyValueBlock } from "@/components/rich/KeyValueBlock";
import {
  LazyChartBlock,
  LazyChemistryBlock,
  LazyFunctionGraphBlock,
  LazyGeometryBlock,
  LazyMermaidBlock,
  LazyMolecule3DBlock,
} from "@/components/rich/LazyHeavyRich";
import { MathBlock } from "@/components/rich/MathView";
import { MessagePreview } from "@/components/rich/MessagePreview";
import { QuoteBlock } from "@/components/rich/QuoteBlock";
import { SocialPostCard } from "@/components/rich/SocialPostCard";
import { StepList } from "@/components/rich/StepList";
import { looksLikeLatexFence } from "@/lib/mathFenceRetag";
import { isAnswerLang } from "@/lib/copyBlock";
import { fenceIdForLang } from "@/lib/fenceRegistry";
import {
  detectJsonRichFenceKind,
  isMessageLang,
  isStructuredFenceLang,
  parseCalloutKind,
  parseCollapsible,
  parseComparison,
  parseEmailDraft,
  parseKeyValue,
  parseQuoteAttribution,
  parseSocialPlatform,
  parseSteps,
} from "@/lib/richBlocks";

function mathFenceKey(content: string, tokenIndex?: number): string {
  return tokenIndex != null ? `math:${content}#${tokenIndex}` : `math:${content}`;
}

export function renderRichFence(
  lang: string,
  content: string,
  key: string,
  tokenIndex?: number,
): ReactNode | null {
  const l = lang.trim().toLowerCase();
  if (!isStructuredFenceLang(l)) {
    if (looksLikeLatexFence(content) && (l === "json" || l === "latex" || l === "tex" || l === "")) {
      // Content-derived key, not the caller-supplied `key` (which
      // react-native-markdown-display regenerates on every re-parse while
      // streaming) — the same latex across re-parses must map to the same
      // key, or MathBlock's WebView-backed renderer unmounts/remounts (a
      // full WebView reload, visible as a flicker) every ~48ms even though
      // nothing actually changed.
      return <MathBlock key={mathFenceKey(content, tokenIndex)} latex={content} />;
    }
    // Same class of instruction-drift as the LaTeX fallback above — the
    // model routinely emits ```json (or an untagged fence) instead of the
    // ```geometry / ```graph it's told to use for diagrams.
    if (l === "json" || l === "") {
      const kind = detectJsonRichFenceKind(content);
      if (kind === "geometry") return <LazyGeometryBlock key={key} content={content} />;
      if (kind === "graph") return <LazyFunctionGraphBlock key={key} content={content} />;
    }
    return null;
  }

  if (l === "email") {
    const draft = parseEmailDraft(content) ?? { body: content };
    return <EmailCard key={key} draft={draft} />;
  }

  if (l === "quote" || l === "blockquote") {
    const { quote, author } = parseQuoteAttribution(content);
    if (!quote) return null;
    return <QuoteBlock key={key} quote={quote} author={author} />;
  }

  if (isMessageLang(l)) {
    return <MessagePreview key={key} text={content} />;
  }

  const social = parseSocialPlatform(l);
  if (social) {
    return <SocialPostCard key={key} platform={social} text={content} />;
  }

  if (fenceIdForLang(l) === "math") {
    return <MathBlock key={mathFenceKey(content, tokenIndex)} latex={content} />;
  }

  if (isAnswerLang(l)) {
    return <AnswerBlock key={key} content={content} />;
  }

  if (l === "geometry") {
    return <LazyGeometryBlock key={key} content={content} />;
  }

  if (l === "graph") {
    return <LazyFunctionGraphBlock key={key} content={content} />;
  }

  if (l === "places") {
    const places = parsePlacesJson(content);
    if (places.length > 0) return <PlacesListBlock key={key} places={places} />;
    return null;
  }

  if (l === "clock" || l === "time") {
    return <CircularClockBlock key={key} content={content} />;
  }

  if (
    l === "callout" ||
    l.startsWith("callout-") ||
    ["tip", "note", "warning", "info", "important"].includes(l)
  ) {
    return (
      <CalloutBlock key={key} kind={parseCalloutKind(l)} content={content} />
    );
  }

  if (l === "details" || l === "collapse" || l === "summary") {
    const draft = parseCollapsible(l, content);
    return <CollapsibleBlock key={key} title={draft.title} body={draft.body} />;
  }

  if (l === "compare" || l === "comparison" || l === "pros") {
    const data = parseComparison(content);
    if (data) return <ComparisonBlock key={key} data={data} />;
  }

  if (l === "kv" || l === "keyvalue" || l === "fields") {
    return <KeyValueBlock key={key} rows={parseKeyValue(content)} />;
  }

  if (l === "steps" || l === "step") {
    return <StepList key={key} steps={parseSteps(content)} />;
  }

  // Mermaid / graph diagrams (async-split vendors — see LazyHeavyRich)
  if (l === "mermaid") {
    return <LazyMermaidBlock key={key} content={content} />;
  }

  // Chemistry structures (SMILES — async-split SmilesDrawer)
  if (l === "smiles" || l === "chemistry") {
    return <LazyChemistryBlock key={key} content={content} />;
  }

  // 3D molecule viewer (SDF — async-split 3Dmol.js)
  if (l === "molecule3d" || l === "mol3d" || l === "3dmol") {
    return <LazyMolecule3DBlock key={key} content={content} />;
  }

  // Chart / data visualization (vega-lite — async-split vendors)
  if (l === "chart" || l === "vega" || l === "vega-lite" || l === "plot") {
    return <LazyChartBlock key={key} content={content} />;
  }

  return null;
}

export function renderCopyStyleBlock(
  lang: string,
  content: string,
  key: string,
): ReactNode | null {
  const l = lang.trim().toLowerCase();
  if (l === "email") {
    const draft = parseEmailDraft(content);
    if (draft) return <EmailCard key={key} draft={draft} />;
  }
  if (isMessageLang(l)) {
    return (
      <MessagePreview
        key={key}
        text={content}
        label={l === "reply" ? i18n.t("rich.reply_draft") : i18n.t("rich.message_draft")}
      />
    );
  }
  const social = parseSocialPlatform(l);
  if (social) {
    return <SocialPostCard key={key} platform={social} text={content} />;
  }
  const draft = parseEmailDraft(content);
  if (draft) {
    return <EmailCard key={key} draft={draft} />;
  }
  return null;
}
