/**
 * Async-split Mermaid (~3.4MB), Vega (~0.85MB), and SmilesDrawer (~0.25MB)
 * off the chat import graph. RichFence used to static-import heavy vendors;
 * any markdown message pulled them even when unused.
 */
import React, { Suspense } from "react";
import { ActivityIndicator, View } from "react-native";

const MermaidBlockLazy = React.lazy(() =>
  import("@/components/rich/MermaidBlock").then((m) => ({ default: m.MermaidBlock })),
);

const ChartBlockLazy = React.lazy(() =>
  import("@/components/rich/ChartBlock").then((m) => ({ default: m.ChartBlock })),
);

const ChemistryBlockLazy = React.lazy(() =>
  import("@/components/rich/ChemistryBlock").then((m) => ({ default: m.ChemistryBlock })),
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
