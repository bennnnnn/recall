/**
 * Async-split Mermaid (~3.4MB), Vega (~0.85MB), SmilesDrawer (~0.25MB),
 * Web preview, clock, and geometry/graph SVG blocks off the chat import graph.
 */
import React, { Suspense, useMemo } from "react";
import { ActivityIndicator, useWindowDimensions, View } from "react-native";

import { FIGURE_TITLE_HEIGHT, figureWidth } from "@/components/rich/figure";
import {
  parseSimulationSpec,
  SIMULATION_HEIGHT,
  SIMULATION_MIN_HEIGHT,
  SIMULATION_PAD,
  simulationIsAnimated,
  simulationViewportHeight,
} from "@/lib/physics/simulation";
import { Space } from "@/lib/space";

const MermaidBlockLazy = React.lazy(() =>
  import("@/components/rich/MermaidBlock").then((m) => ({ default: m.MermaidBlock })),
);

const ChartBlockLazy = React.lazy(() =>
  import("@/components/rich/ChartBlock").then((m) => ({ default: m.ChartBlock })),
);

const ChemistryBlockLazy = React.lazy(() =>
  import("@/components/rich/ChemistryBlock").then((m) => ({ default: m.ChemistryBlock })),
);

const MoleculeCardLazy = React.lazy(() =>
  import("@/components/rich/MoleculeCard").then((m) => ({ default: m.MoleculeCard })),
);

const Molecule3DBlockLazy = React.lazy(() =>
  import("@/components/rich/Molecule3DBlock").then((m) => ({ default: m.Molecule3DBlock })),
);

const GeometryBlockLazy = React.lazy(() =>
  import("@/components/rich/GeometryBlock").then((m) => ({ default: m.GeometryBlock })),
);

const FunctionGraphBlockLazy = React.lazy(() =>
  import("@/components/rich/FunctionGraphBlock").then((m) => ({ default: m.FunctionGraphBlock })),
);

const SimulationBlockLazy = React.lazy(() =>
  import("@/components/rich/SimulationBlock").then((m) => ({ default: m.SimulationBlock })),
);

const CircularClockBlockLazy = React.lazy(() =>
  import("@/components/rich/CircularClockBlock").then((m) => ({
    default: m.CircularClockBlock,
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

export function LazyMermaidBlock({ content }: { content: string }) {
  return (
    <Suspense fallback={<RichLoadPlaceholder height={220} />}>
      <MermaidBlockLazy content={content} />
    </Suspense>
  );
}

export function LazyChartBlock({ content }: { content: string }) {
  return (
    <Suspense fallback={<RichLoadPlaceholder height={350} />}>
      <ChartBlockLazy content={content} />
    </Suspense>
  );
}

export function LazyChemistryBlock({ content }: { content: string }) {
  return (
    <Suspense fallback={<RichLoadPlaceholder height={240} />}>
      <ChemistryBlockLazy content={content} />
    </Suspense>
  );
}

export function LazyMoleculeCard({ content }: { content: string }) {
  return (
    <Suspense fallback={<RichLoadPlaceholder height={240} />}>
      <MoleculeCardLazy content={content} />
    </Suspense>
  );
}

export function LazyMolecule3DBlock({ content }: { content: string }) {
  return (
    <Suspense fallback={<RichLoadPlaceholder height={280} />}>
      <Molecule3DBlockLazy content={content} />
    </Suspense>
  );
}

export function LazyGeometryBlock({ content }: { content: string }) {
  return (
    <Suspense fallback={<RichLoadPlaceholder height={220} />}>
      <GeometryBlockLazy content={content} />
    </Suspense>
  );
}

export function LazyFunctionGraphBlock({ content }: { content: string }) {
  return (
    <Suspense fallback={<RichLoadPlaceholder height={280} />}>
      <FunctionGraphBlockLazy content={content} />
    </Suspense>
  );
}

/**
 * The height the scene will take once loaded — title, canvas sized to the
 * scene's aspect, and the play button when something moves — so a list cell
 * does not jump when the chunk arrives. Unreadable content keeps the old
 * fixed guess; the block shows a one-line fallback for it anyway.
 */
export function simulationPlaceholderHeight(content: string, screenWidth: number): number {
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
  const height = useMemo(
    () => simulationPlaceholderHeight(content, screenWidth),
    [content, screenWidth],
  );
  return (
    <Suspense fallback={<RichLoadPlaceholder height={height} />}>
      <SimulationBlockLazy content={content} />
    </Suspense>
  );
}

export function LazyCircularClockBlock({ content }: { content: string }) {
  return (
    <Suspense fallback={<RichLoadPlaceholder height={340} />}>
      <CircularClockBlockLazy content={content} />
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
  const visibleLines = Math.min(code.split("\n").length, 14);
  const placeholderHeight = 112 + visibleLines * 20;
  return (
    <Suspense fallback={<RichLoadPlaceholder height={placeholderHeight} />}>
      <WebPreviewCodeBlockLazy code={code} lang={lang} />
    </Suspense>
  );
}
