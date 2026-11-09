/**
 * Async-split Mermaid (~3.4MB), Vega (~0.85MB), SmilesDrawer (~0.25MB),
 * Web preview, clock, geometry/graph SVG blocks, physics scenes and the
 * parsers that size a scene's placeholder off the chat import graph.
 */
import React, { Suspense, useEffect, useMemo, useState, type ComponentType } from "react";
import { useWindowDimensions, View } from "react-native";
import { useTranslation } from "react-i18next";

import { FIGURE_TITLE_HEIGHT } from "@/components/rich/figure";
import { graphPlaceholderHeight } from "@/components/rich/graphPlaceholder";
import { diagramKind } from "@/lib/physics/diagramKind";
import { SIMULATION_HEIGHT } from "@/lib/physics/simulation/viewport";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { SkeletonBlock } from "@/ui/feedback/SkeletonLoader";

/** The height each block's placeholder holds while its chunk loads, close to the drawn card. */
const PLACEHOLDER_HEIGHT = {
  mermaid: 220,
  chart: 350,
  chemistry: 240,
  molecule: 240,
  molecule3d: 280,
  geometry: 220,
  clock: 340,
} as const;

/** A web preview's spinner: its chrome plus up to 14 visible code lines. */
const WEB_PREVIEW_CHROME_HEIGHT = 112;
const WEB_PREVIEW_LINE_HEIGHT = 20;
const WEB_PREVIEW_MAX_LINES = 14;

// The figures under a STEM answer: one loader each, shared by the block and the preload.
const loadSimulationBlock = () => import("@/components/rich/SimulationBlock");
const loadPhysicsDiagram = () => import("@/components/rich/diagrams/PhysicsDiagram");
const loadFunctionGraphBlock = () => import("@/components/rich/FunctionGraphBlock");

const SimulationBlockLazy = React.lazy(() =>
  loadSimulationBlock().then((m) => ({ default: m.SimulationBlock })),
);

const PhysicsDiagramLazy = React.lazy(() =>
  loadPhysicsDiagram().then((m) => ({ default: m.PhysicsDiagram })),
);

const WebPreviewCodeBlockLazy = React.lazy(() =>
  import("@/components/WebPreviewCodeBlock").then((m) => ({
    default: m.WebPreviewCodeBlock,
  })),
);

/**
 * The card's own room while its renderer loads, drawn as the kit's quiet skeleton (a title
 * line over the figure's area), never a bare spinner in an empty gap.
 */
function RichLoadPlaceholder({ height }: { height: number }) {
  const { t } = useTranslation();
  const titleLine = FIGURE_TITLE_HEIGHT - Space.xs;
  const area = Math.max(0, height - Space.xs * 3 - titleLine);
  return (
    <View
      testID="rich-load-placeholder"
      accessible
      accessibilityRole="progressbar"
      accessibilityLabel={t("common.loading")}
      style={{ height, paddingVertical: Space.xs, gap: Space.xs, alignItems: "center" }}
    >
      <SkeletonBlock width="40%" height={titleLine} />
      <SkeletonBlock height={area} borderRadius={Radius.md} />
    </View>
  );
}

type ContentBlockProps = { content: string };

/**
 * A block drawn from a fence body, loaded on first use behind a placeholder of `height`
 * (the fence's own, when it can say). The `import()` stays a literal at each call so Metro
 * splits it.
 */
function lazyContentBlock(
  load: () => Promise<{ default: ComponentType<ContentBlockProps> }>,
  height: number | ((content: string) => number),
): ComponentType<ContentBlockProps> {
  const Block = React.lazy(load);
  return function LazyContentBlock({ content }: ContentBlockProps) {
    const room = useMemo(() => (typeof height === "number" ? height : height(content)), [content]);
    return (
      <Suspense fallback={<RichLoadPlaceholder height={room} />}>
        <Block content={content} />
      </Suspense>
    );
  };
}

export const LazyMermaidBlock = lazyContentBlock(
  () => import("@/components/rich/MermaidBlock").then((m) => ({ default: m.MermaidBlock })),
  PLACEHOLDER_HEIGHT.mermaid,
);

export const LazyChartBlock = lazyContentBlock(
  () => import("@/components/rich/ChartBlock").then((m) => ({ default: m.ChartBlock })),
  PLACEHOLDER_HEIGHT.chart,
);

export const LazyChemistryBlock = lazyContentBlock(
  () => import("@/components/rich/ChemistryBlock").then((m) => ({ default: m.ChemistryBlock })),
  PLACEHOLDER_HEIGHT.chemistry,
);

export const LazyMoleculeCard = lazyContentBlock(
  () => import("@/components/rich/MoleculeCard").then((m) => ({ default: m.MoleculeCard })),
  PLACEHOLDER_HEIGHT.molecule,
);

export const LazyMolecule3DBlock = lazyContentBlock(
  () => import("@/components/rich/Molecule3DBlock").then((m) => ({ default: m.Molecule3DBlock })),
  PLACEHOLDER_HEIGHT.molecule3d,
);

export const LazyGeometryBlock = lazyContentBlock(
  () => import("@/components/rich/GeometryBlock").then((m) => ({ default: m.GeometryBlock })),
  PLACEHOLDER_HEIGHT.geometry,
);

export const LazyFunctionGraphBlock = lazyContentBlock(
  () => loadFunctionGraphBlock().then((m) => ({ default: m.FunctionGraphBlock })),
  graphPlaceholderHeight,
);

export const LazyCircularClockBlock = lazyContentBlock(
  () =>
    import("@/components/rich/CircularClockBlock").then((m) => ({
      default: m.CircularClockBlock,
    })),
  PLACEHOLDER_HEIGHT.clock,
);

type SimulationSizing = typeof import("@/components/rich/simulationPlaceholder");

/** The fence's exact placeholder height comes from the physics parsers, loaded on first use. */
let simulationSizing: SimulationSizing | null = null;
let simulationSizingLoad: Promise<SimulationSizing> | null = null;

function loadSimulationSizing(): Promise<SimulationSizing> {
  simulationSizingLoad ??= import("@/components/rich/simulationPlaceholder").then(
    (sizing) => {
      simulationSizing = sizing;
      return sizing;
    },
    (error: unknown) => {
      simulationSizingLoad = null;
      throw error;
    },
  );
  return simulationSizingLoad;
}

/**
 * Loads the figures' renderers and the scene sizing parsers ahead of the first answer that
 * draws one (the root layout calls this once the launch has settled). A picture then draws
 * as its reply settles, where it waited for its chunk behind a placeholder; on a
 * development build that chunk took Metro about 6 s to build the first time.
 */
export function preloadFigures(): void {
  Promise.all([
    loadSimulationSizing(),
    loadSimulationBlock(),
    loadPhysicsDiagram(),
    loadFunctionGraphBlock(),
  ]).catch(() => {});
}

/** The sizing module once loaded; the first scene of a session asks for it. */
function useSimulationSizing(): SimulationSizing | null {
  const [sizing, setSizing] = useState(simulationSizing);
  useEffect(() => {
    if (sizing) return;
    let current = true;
    loadSimulationSizing().then(
      (loaded) => {
        if (current) setSizing(loaded);
      },
      () => {},
    );
    return () => {
      current = false;
    };
  }, [sizing]);
  return sizing;
}

export function LazySimulationBlock({ content }: { content: string }) {
  const { width: screenWidth } = useWindowDimensions();
  // A circuit, a ray diagram or a wave has no bodies to walk: its own renderer.
  const kind = useMemo(() => diagramKind(content), [content]);
  const sizing = useSimulationSizing();
  // Until the sizing module is in (a moment, once per session), the usual scene height.
  const height = useMemo(
    () =>
      sizing
        ? sizing.simulationFencePlaceholderHeight(content, kind, screenWidth)
        : SIMULATION_HEIGHT,
    [content, kind, screenWidth, sizing],
  );
  return (
    <Suspense fallback={<RichLoadPlaceholder height={height} />}>
      {kind ? (
        <PhysicsDiagramLazy content={content} kind={kind} />
      ) : (
        <SimulationBlockLazy content={content} />
      )}
    </Suspense>
  );
}

export function LazyWebPreviewCodeBlock({
  code,
  lang = "html",
}: {
  code: string;
  lang?: string;
}) {
  const visibleLines = Math.min(code.split("\n").length, WEB_PREVIEW_MAX_LINES);
  const placeholderHeight = WEB_PREVIEW_CHROME_HEIGHT + visibleLines * WEB_PREVIEW_LINE_HEIGHT;
  return (
    <Suspense fallback={<RichLoadPlaceholder height={placeholderHeight} />}>
      <WebPreviewCodeBlockLazy code={code} lang={lang} />
    </Suspense>
  );
}
