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
import type { FenceId } from "@/lib/fenceRegistry";
import { fenceIdForLang } from "@/lib/fenceRegistry";
import {
  isMessageLang,
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

/** Render a registry fence by id — no lang-string soup, no content heuristics. */
export function renderRichFenceById(
  id: FenceId,
  lang: string,
  content: string,
  key: string,
  tokenIndex?: number,
): ReactNode | null {
  switch (id) {
    case "email": {
      const draft = parseEmailDraft(content) ?? { body: content };
      return <EmailCard key={key} draft={draft} />;
    }
    case "quote": {
      const { quote, author } = parseQuoteAttribution(content);
      if (!quote) return null;
      return <QuoteBlock key={key} quote={quote} author={author} />;
    }
    case "message":
      return <MessagePreview key={key} text={content} />;
    case "social": {
      const social = parseSocialPlatform(lang);
      if (!social) return null;
      return <SocialPostCard key={key} platform={social} text={content} />;
    }
    case "math":
      return <MathBlock key={mathFenceKey(content, tokenIndex)} latex={content} />;
    case "answer":
      return <AnswerBlock key={key} content={content} />;
    case "geometry":
      return <LazyGeometryBlock key={key} content={content} />;
    case "graph":
      return <LazyFunctionGraphBlock key={key} content={content} />;
    case "places": {
      const places = parsePlacesJson(content);
      if (places.length > 0) return <PlacesListBlock key={key} places={places} />;
      return null;
    }
    case "clock":
      return <CircularClockBlock key={key} content={content} />;
    case "callout":
      return <CalloutBlock key={key} kind={parseCalloutKind(lang)} content={content} />;
    case "collapsible": {
      const draft = parseCollapsible(lang, content);
      return <CollapsibleBlock key={key} title={draft.title} body={draft.body} />;
    }
    case "comparison": {
      const data = parseComparison(content);
      if (data) return <ComparisonBlock key={key} data={data} />;
      return null;
    }
    case "keyvalue":
      return <KeyValueBlock key={key} rows={parseKeyValue(content)} />;
    case "steps":
      return <StepList key={key} steps={parseSteps(content)} />;
    case "mermaid":
      return <LazyMermaidBlock key={key} content={content} />;
    case "chemistry":
      return <LazyChemistryBlock key={key} content={content} />;
    case "molecule3d":
      return <LazyMolecule3DBlock key={key} content={content} />;
    case "chart":
      return <LazyChartBlock key={key} content={content} />;
    case "copy":
    case "sources":
    case "learning_launch":
      return null;
    default:
      return null;
  }
}

export function renderRichFence(
  lang: string,
  content: string,
  key: string,
  tokenIndex?: number,
): ReactNode | null {
  const id = fenceIdForLang(lang);
  if (!id) return null;
  return renderRichFenceById(id, lang, content, key, tokenIndex);
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
