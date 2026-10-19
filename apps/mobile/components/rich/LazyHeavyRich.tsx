/**
 * Async-split Mermaid (~3.4MB), Vega (~0.85MB), SmilesDrawer (~0.25MB),
 * Web preview, clock, and geometry/graph SVG blocks off the chat import graph.
 */
import React, { Suspense, useMemo, type ComponentType } from "react";
import { ActivityIndicator, useWindowDimensions, View } from "react-native";

import { physicsDiagramPlaceholderHeight } from "@/components/rich/diagrams/placeholder";
import { FIGURE_TITLE_HEIGHT, figureWidth } from "@/components/rich/figure";
import { diagramKind } from "@/lib/physics/diagramKind";
import {
  parseSimulationSpec,
  SIMULATION_HEIGHT,
  SIMULATION_MIN_HEIGHT,
  SIMULATION_PAD,
  simulationIsAnimated,
  simulationViewportHeight,
} from "@/lib/physics/simulation";
import { Space } from "@/lib/space";

/** The height each block's spinner holds while its chunk loads, close to the drawn card. */
const PLACEHOLDER_HEIGHT = {
  mermaid: 220,
  chart: 350,
  chemistry: 240,
  molecule: 240,
  molecule3d: 280,
  geometry: 220,
  graph: 280,
  clock: 340,
} as const;

/** A web preview's spinner: its chrome plus up to 14 visible code lines. */
const WEB_PREVIEW_CHROME_HEIGHT = 112;
const WEB_PREVIEW_LINE_HEIGHT = 20;
const WEB_PREVIEW_MAX_LINES = 14;

const SimulationBlockLazy = React.lazy(() =>
  import("@/components/rich/SimulationBlock").then((m) => ({
    default: m.SimulationBlock,
  })),
);

const PhysicsDiagramLazy = React.lazy(() =>
  import("@/components/rich/diagrams/PhysicsDiagram").then((m) => ({
    default: m.PhysicsDiagram,
  })),
);

const WebPreviewCodeBlockLazy = React.lazy(() =>
  import("@/components/WebPreviewCodeBlock").then((m) => ({
    default: m.WebPreviewCodeBlock,
  })),
);

function RichLoadPlaceholder({ height }: { height: number }) {
  return (
    <View style={{ height, alignItems: "center", justifyContent: "center" }}>
      <ActivityIndicator />
    </View>
  );
}

type ContentBlockProps = { content: string };

/**
 * A block drawn from a fence body, loaded on first use behind a spinner of
 * `height`. The `import()` stays a literal at each call so Metro splits it.
 */
function lazyContentBlock(
  load: () => Promise<{ default: ComponentType<ContentBlockProps> }>,
  height: number,
): ComponentType<ContentBlockProps> {
  const Block = React.lazy(load);
  return function LazyContentBlock({ content }: ContentBlockProps) {
    return (
      <Suspense fallback={<RichLoadPlaceholder height={height} />}>
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
  () =>
    import("@/components/rich/FunctionGraphBlock").then((m) => ({
      default: m.FunctionGraphBlock,
    })),
  PLACEHOLDER_HEIGHT.graph,
);

export const LazyCircularClockBlock = lazyContentBlock(
  () =>
    import("@/components/rich/CircularClockBlock").then((m) => ({
      default: m.CircularClockBlock,
    })),
  PLACEHOLDER_HEIGHT.clock,
);

/**
 * The height the scene will take once loaded — title, canvas sized to the
 * scene's aspect, and the play button when something moves — so a list cell
 * does not jump when the chunk arrives. Unreadable content keeps the old
 * fixed guess; the block shows a one-line fallback for it anyway.
 */
export function simulationPlaceholderHeight(
  content: string,
  screenWidth: number,
): number {
  const spec = parseSimulationSpec(content);
  if (!spec) return SIMULATION_HEIGHT;
  const canvas = simulationViewportHeight(
    spec,
    figureWidth(screenWidth),
    SIMULATION_PAD,
    SIMULATION_MIN_HEIGHT,
    SIMULATION_HEIGHT,
  );
  const control = simulationIsAnimated(spec) ? Space.xxs + Space.minTouch : 0;
  return Space.xs * 2 + FIGURE_TITLE_HEIGHT + canvas + control;
}

export function LazySimulationBlock({ content }: { content: string }) {
  const { width: screenWidth } = useWindowDimensions();
  // A circuit, a ray diagram or a wave has no bodies to walk: its own renderer.
  const kind = useMemo(() => diagramKind(content), [content]);
  const height = useMemo(
    () =>
      kind
        ? physicsDiagramPlaceholderHeight(content, screenWidth)
        : simulationPlaceholderHeight(content, screenWidth),
    [content, kind, screenWidth],
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
