import { ReactNode } from "react";

import { PlacesListBlock } from "@/components/PlacesListBlock";
import { CalloutBlock } from "@/components/rich/CalloutBlock";
import { parsePlacesJson } from "@/lib/placesList";
import { ChartBlock } from "@/components/rich/ChartBlock";
import { CollapsibleBlock } from "@/components/rich/CollapsibleBlock";
import { ComparisonBlock } from "@/components/rich/ComparisonBlock";
import { CircularClockBlock } from "@/components/rich/CircularClockBlock";
import { EmailCard } from "@/components/rich/EmailCard";
import { FunctionGraphBlock } from "@/components/rich/FunctionGraphBlock";
import { GeometryBlock } from "@/components/rich/GeometryBlock";
import { KeyValueBlock } from "@/components/rich/KeyValueBlock";
import { MathBlock } from "@/components/rich/MathView";
import { MermaidBlock } from "@/components/rich/MermaidBlock";
import { MessagePreview } from "@/components/rich/MessagePreview";
import { SocialPostCard } from "@/components/rich/SocialPostCard";
import { StepList } from "@/components/rich/StepList";
import {
  fenceContentAsGeometry,
  fenceContentAsGraph,
  looksLikeLatexFence,
} from "@/lib/mathFenceRetag";
import {
  isMessageLang,
  isStructuredFenceLang,
  parseCalloutKind,
  parseCollapsible,
  parseComparison,
  parseEmailDraft,
  parseKeyValue,
  parseSocialPlatform,
  parseSteps,
} from "@/lib/richBlocks";

export function renderRichFence(
  lang: string,
  content: string,
  key: string,
): ReactNode | null {
  const l = lang.trim().toLowerCase();
  if (!isStructuredFenceLang(l)) {
    if (fenceContentAsGeometry(content)) {
      return <GeometryBlock key={key} content={content} />;
    }
    if (fenceContentAsGraph(content)) {
      return <FunctionGraphBlock key={key} content={content} />;
    }
    if (looksLikeLatexFence(content) && (l === "json" || l === "latex" || l === "tex" || l === "")) {
      return <MathBlock key={key} latex={content} />;
    }
    return null;
  }

  if (l === "email") {
    const draft = parseEmailDraft(content) ?? { body: content };
    return <EmailCard key={key} draft={draft} />;
  }

  if (isMessageLang(l)) {
    return <MessagePreview key={key} text={content} />;
  }

  const social = parseSocialPlatform(l);
  if (social) {
    return <SocialPostCard key={key} platform={social} text={content} />;
  }

  if (l === "math") {
    return <MathBlock key={key} latex={content} />;
  }

  if (l === "geometry") {
    return <GeometryBlock key={key} content={content} />;
  }

  if (l === "graph") {
    return <FunctionGraphBlock key={key} content={content} />;
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

  // Mermaid / graph diagrams
  if (l === "mermaid") {
    return <MermaidBlock key={key} content={content} />;
  }

  // Chart / data visualization (vega-lite, chart.js, plot)
  if (l === "chart" || l === "vega" || l === "vega-lite" || l === "plot") {
    return <ChartBlock key={key} content={content} />;
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
        label={l === "reply" ? "Reply draft" : "Message draft"}
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
