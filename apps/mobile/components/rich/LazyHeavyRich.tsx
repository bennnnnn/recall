/**
 * Async-split Mermaid (~3.4MB) and Vega (~0.85MB) off the chat import graph.
 * RichFence used to static-import both; any markdown message pulled the vendors
 * even when the turn never used a diagram/chart fence.
 */
import React, { Suspense } from "react";
import { ActivityIndicator, View } from "react-native";

const MermaidBlockLazy = React.lazy(() =>
  import("@/components/rich/MermaidBlock").then((m) => ({ default: m.MermaidBlock })),
);

const ChartBlockLazy = React.lazy(() =>
  import("@/components/rich/ChartBlock").then((m) => ({ default: m.ChartBlock })),
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
