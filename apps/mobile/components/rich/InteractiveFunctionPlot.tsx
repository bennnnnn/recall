import {
  lazy,
  Suspense,
  useCallback,
  useId,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
  type LayoutChangeEvent,
} from "react-native";
import { GestureDetector, GestureHandlerRootView } from "react-native-gesture-handler";
import Animated from "react-native-reanimated";
import { useTranslation } from "react-i18next";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Icon } from "@/components/Icon";
import { GraphCanvas, GRAPH_AXIS_PAD } from "@/components/rich/GraphCanvas";
import {
  type DrawnSeries,
  drawGraphSeries,
  useGraphSeries,
  useGraphViewport,
} from "@/hooks/useInteractiveGraph";
import { useSheetPanDismiss } from "@/hooks/useSheetPanDismiss";
import { useSkiaGraphViewport } from "@/hooks/useSkiaGraphViewport";
import { CODE_FONT } from "@/lib/fonts";
import { formatGraphExpr, type GraphSpec } from "@/lib/math/graphBlock";
import { defaultInteractiveBounds, expandGraphView } from "@/lib/math/graphViewport";
import { isSkiaAvailable } from "@/lib/skiaAvailability";
import { IconSize } from "@/lib/icons";
import { useReduceMotion } from "@/lib/reduceMotion";
import { Space } from "@/lib/space";
import { Theme } from "@/lib/theme";

const CHART_HEIGHT = 220;
const MODAL_LIST_MAX = 220;
const MODAL_PLOT_MIN = 200;
/** Skia explorer samples a 3x window at 3x density for mid-gesture runway. */
const SKIA_SAMPLE_EXPAND = 3;
const SKIA_SAMPLES = 480;

// Skia stays out of the import graph unless the modal actually opens on a
// build that has the native module (Expo Go keeps the SVG explorer).
const SkiaGraphExplorerLazy = lazy(() =>
  import("@/components/rich/skia/SkiaGraphExplorer").then((m) => ({
    default: m.SkiaGraphExplorer,
  })),
);

type Props = {
  spec: GraphSpec;
  chartWidth: number;
  styles: {
    wrap: object;
    title: object;
  };
  theme: Theme;
};

export function InteractiveFunctionPlot({ spec, chartWidth, styles, theme }: Props) {
  const { t } = useTranslation();
  const insets = useSafeAreaInsets();
  const { width: screenW, height: screenH } = useWindowDimensions();
  const [open, setOpen] = useState(false);
  const [plotWidth, setPlotWidth] = useState(chartWidth);
  const closeModal = useCallback(() => setOpen(false), []);
  const cardClipId = useId().replace(/:/g, "");
  const modalClipId = useId().replace(/:/g, "");
  const explorerStyles = useMemo(() => makeExplorerStyles(theme), [theme]);
  const verticalX = spec.type === "vertical" ? spec.x : undefined;
  const isVerticalLine = verticalX != null;
  const editable = spec.type === "function";
  const seedExprs = hasCurve2(spec) ? [spec.expr, spec.expr2 ?? ""] : [spec.expr];
  const seedFallbacks = hasCurve2(spec)
    ? [
        { points: spec.points, segments: spec.segments },
        { points: spec.points2 ?? [], segments: spec.segments2 },
      ]
    : [{ points: spec.points, segments: spec.segments }];
  const { series, canAdd, setExpr, toggleVisible, removeSeries, addSeries } = useGraphSeries(
    seedExprs,
    seedFallbacks,
  );
  const palette = theme.graphSeries;
  const variable = spec.variable ?? "x";
  const cardWidth = Math.max(1, plotWidth);
  const cardAspect = (cardWidth - GRAPH_AXIS_PAD * 2) / (CHART_HEIGHT - GRAPH_AXIS_PAD * 2 || 1);
  const cardBounds = useMemo(() => defaultInteractiveBounds(cardAspect), [cardAspect]);
  const cardDrawn = useMemo(
    () => series.map((row, i) => drawGraphSeries(row, palette[i % palette.length], variable, cardBounds)),
    [cardBounds, palette, series, variable],
  );
  const modalWidth = Math.max(1, screenW - insets.left - insets.right);
  const fallbackModalH = Math.max(MODAL_PLOT_MIN, screenH - insets.top - insets.bottom - 200);
  const [modalPlot, setModalPlot] = useState({ width: modalWidth, height: fallbackModalH });
  const viewport = useGraphViewport({
    width: modalPlot.width,
    height: modalPlot.height,
    pad: GRAPH_AXIS_PAD,
  });
  const skiaExplorer = isSkiaAvailable();
  const modalAspect =
    (modalPlot.width - GRAPH_AXIS_PAD * 2) / (modalPlot.height - GRAPH_AXIS_PAD * 2 || 1);
  const modalInitialView = useMemo(() => defaultInteractiveBounds(modalAspect), [modalAspect]);
  const onCardLayout = (e: LayoutChangeEvent) => {
    const w = Math.round(e.nativeEvent.layout.width);
    if (w > 0 && w !== plotWidth) setPlotWidth(w);
  };
  const onModalPlotLayout = (e: LayoutChangeEvent) => {
    const { width, height } = e.nativeEvent.layout;
    const w = Math.round(width);
    const h = Math.round(height);
    if (w > 0 && h > 0 && (w !== modalPlot.width || h !== modalPlot.height)) {
      setModalPlot({ width: w, height: h });
    }
  };
  // The Skia explorer pans/zooms on the UI thread against samples taken over
  // an expanded window; viewport.bounds only moves on gesture-end commits.
  const sampleBounds = useMemo(
    () => (skiaExplorer ? expandGraphView(viewport.bounds, SKIA_SAMPLE_EXPAND) : viewport.bounds),
    [skiaExplorer, viewport.bounds],
  );
  const modalDrawn = useMemo(
    () =>
      series.map((row, i) =>
        drawGraphSeries(
          row,
          palette[i % palette.length],
          variable,
          sampleBounds,
          skiaExplorer ? SKIA_SAMPLES : 160,
        ),
      ),
    [palette, series, variable, sampleBounds, skiaExplorer],
  );
  const customTitle =
    spec.title != null && spec.title.trim() !== "" && spec.title.trim() !== spec.expr
      ? formatGraphExpr(spec.title)
      : null;
  const seriesListRef = useRef<ScrollView>(null);
  const addSeriesAndReveal = () => {
    addSeries();
    requestAnimationFrame(() => {
      seriesListRef.current?.scrollToEnd({ animated: true });
    });
  };
  const seriesEditor = (rows: DrawnSeries[], mode: "card" | "modal") =>
    editable ? (
      <SeriesList
        rows={rows}
        theme={theme}
        styles={explorerStyles}
        canAdd={canAdd}
        scrollRef={mode === "modal" ? seriesListRef : undefined}
        onChangeExpr={setExpr}
        onToggle={toggleVisible}
        onRemove={removeSeries}
        onAdd={mode === "modal" ? addSeriesAndReveal : addSeries}
      />
    ) : null;

  return (
    <View style={[styles.wrap, explorerStyles.card]} onLayout={onCardLayout}>
      {customTitle ? <Text style={styles.title}>{customTitle}</Text> : null}
      {isVerticalLine ? (
        <Text style={styles.title}>{formatGraphExpr(spec.title ?? spec.expr)}</Text>
      ) : null}
      <Pressable
        onPress={() => setOpen(true)}
        testID="graph-expand"
        accessibilityRole="button"
        accessibilityLabel={t("rich.expand")}
        style={[explorerStyles.plotPress, { width: cardWidth, height: CHART_HEIGHT }]}
      >
        <GraphCanvas
          spec={spec}
          theme={theme}
          clipId={cardClipId}
          width={cardWidth}
          height={CHART_HEIGHT}
          bounds={cardBounds}
          drawn={cardDrawn}
          verticalX={verticalX}
        />
        <View style={explorerStyles.expandBadge} pointerEvents="none">
          <Icon name="expand-outline" size={16} color={theme.textSecondary} />
        </View>
      </Pressable>
      {open ? null : seriesEditor(cardDrawn, "card")}
      <ExplorerModal
        open={open}
        onClose={closeModal}
        theme={theme}
        styles={explorerStyles}
        insets={insets}
        spec={spec}
        clipId={modalClipId}
        plot={modalPlot}
        onPlotLayout={onModalPlotLayout}
        bounds={viewport.bounds}
        gesture={viewport.gesture}
        drawn={modalDrawn}
        verticalX={verticalX}
        editor={seriesEditor(modalDrawn, "modal")}
        skia={skiaExplorer}
        initialView={modalInitialView}
        onCommitBounds={viewport.commitBounds}
      />
    </View>
  );
}

function hasCurve2(spec: GraphSpec): boolean {
  return spec.type === "function" && !!spec.expr2 && !!spec.points2?.length;
}

function ExplorerModal({
  open,
  onClose,
  theme,
  styles,
  insets,
  spec,
  clipId,
  plot,
  onPlotLayout,
  bounds,
  gesture,
  drawn,
  verticalX,
  editor,
  skia,
  initialView,
  onCommitBounds,
}: {
  open: boolean;
  onClose: () => void;
  theme: Theme;
  styles: ReturnType<typeof makeExplorerStyles>;
  insets: { top: number; bottom: number };
  spec: GraphSpec;
  clipId: string;
  plot: { width: number; height: number };
  onPlotLayout: (e: LayoutChangeEvent) => void;
  bounds: ReturnType<typeof defaultInteractiveBounds>;
  gesture: ReturnType<typeof useGraphViewport>["gesture"];
  drawn: DrawnSeries[];
  verticalX?: number;
  editor: ReactNode;
  skia: boolean;
  initialView: ReturnType<typeof defaultInteractiveBounds>;
  onCommitBounds: (next: ReturnType<typeof defaultInteractiveBounds>) => void;
}) {
  const { t } = useTranslation();
  const reduceMotion = useReduceMotion();
  const { pan, panStyle } = useSheetPanDismiss(open, reduceMotion, onClose);
  const skiaViewport = useSkiaGraphViewport({
    width: plot.width,
    height: plot.height,
    pad: GRAPH_AXIS_PAD,
    initialView,
    onCommit: onCommitBounds,
  });

  return (
    <Modal
      visible={open}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      {open ? (
        <GestureHandlerRootView style={styles.modalRoot}>
          <KeyboardAvoidingView
            style={styles.modalRoot}
            behavior={Platform.OS === "ios" ? "padding" : undefined}
          >
            <Animated.View
              style={[
                styles.modalSheet,
                {
                  backgroundColor: theme.bg,
                  paddingTop: insets.top,
                  paddingBottom: insets.bottom,
                },
                panStyle,
              ]}
            >
              <GestureDetector gesture={pan}>
                <View style={styles.modalToolbar} testID="graph-sheet-handle">
                  <View style={styles.handle} />
                  <Pressable
                    onPress={onClose}
                    testID="graph-close"
                    accessibilityRole="button"
                    accessibilityLabel={t("preview.close")}
                    hitSlop={8}
                    style={styles.closeBtn}
                  >
                    <Icon name="close-outline" size={IconSize.lg} color={theme.text} />
                  </Pressable>
                </View>
              </GestureDetector>
              {skia ? (
                <View
                  collapsable={false}
                  pointerEvents="box-only"
                  accessible
                  accessibilityLabel={t("rich.graph_plot_a11y")}
                  onLayout={onPlotLayout}
                  style={styles.modalPlot}
                >
                  <Suspense
                    fallback={
                      <View style={styles.skiaLoading}>
                        <ActivityIndicator color={theme.textSecondary} />
                      </View>
                    }
                  >
                    <SkiaGraphExplorerLazy
                      drawn={drawn}
                      verticalX={verticalX}
                      xName={spec.variable ?? "x"}
                      yName="y"
                      width={plot.width}
                      height={plot.height}
                      pad={GRAPH_AXIS_PAD}
                      theme={theme}
                      viewport={skiaViewport}
                    />
                  </Suspense>
                </View>
              ) : (
                <GestureDetector gesture={gesture}>
                  <View
                    collapsable={false}
                    pointerEvents="box-only"
                    accessible
                    accessibilityLabel={t("rich.graph_plot_a11y")}
                    onLayout={onPlotLayout}
                    style={styles.modalPlot}
                  >
                    <GraphCanvas
                      spec={spec}
                      theme={theme}
                      clipId={clipId}
                      width={plot.width}
                      height={plot.height}
                      bounds={bounds}
                      drawn={drawn}
                      verticalX={verticalX}
                    />
                  </View>
                </GestureDetector>
              )}
              {editor}
            </Animated.View>
          </KeyboardAvoidingView>
        </GestureHandlerRootView>
      ) : null}
    </Modal>
  );
}

function SeriesList({
  rows,
  theme,
  styles,
  canAdd,
  scrollRef,
  onChangeExpr,
  onToggle,
  onRemove,
  onAdd,
}: {
  rows: DrawnSeries[];
  theme: Theme;
  styles: ReturnType<typeof makeExplorerStyles>;
  canAdd: boolean;
  scrollRef?: RefObject<ScrollView | null>;
  onChangeExpr: (id: string, text: string) => void;
  onToggle: (id: string) => void;
  onRemove: (id: string) => void;
  onAdd: () => void;
}) {
  const { t } = useTranslation();
  const body = (
    <>
      {rows.map((row) => (
        <SeriesRow
          key={row.id}
          row={row}
          theme={theme}
          styles={styles}
          onChangeExpr={(text) => onChangeExpr(row.id, text)}
          onToggle={() => onToggle(row.id)}
          onRemove={() => onRemove(row.id)}
        />
      ))}
      {canAdd ? (
        <Pressable
          onPress={onAdd}
          testID="graph-add-function"
          accessibilityRole="button"
          accessibilityLabel={t("rich.graph_add_function")}
          style={styles.addBtn}
        >
          <Icon name="add-outline" size={16} color={theme.primary} />
          <Text style={styles.addText}>{t("rich.graph_add_function")}</Text>
        </Pressable>
      ) : null}
    </>
  );
  if (scrollRef) {
    return (
      <ScrollView
        ref={scrollRef}
        testID="graph-series-scroll"
        style={styles.modalList}
        contentContainerStyle={styles.modalListContent}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
      >
        {body}
      </ScrollView>
    );
  }
  return <View style={styles.list}>{body}</View>;
}

function SeriesRow({
  row,
  theme,
  styles,
  onChangeExpr,
  onToggle,
  onRemove,
}: {
  row: DrawnSeries;
  theme: Theme;
  styles: ReturnType<typeof makeExplorerStyles>;
  onChangeExpr: (text: string) => void;
  onToggle: () => void;
  onRemove: () => void;
}) {
  const { t } = useTranslation();
  const inputId = row.locked ? "graph-expr-input" : `graph-expr-input-${row.id}`;
  return (
    <View style={styles.row}>
      <View style={[styles.swatch, { backgroundColor: row.color, opacity: row.visible ? 1 : 0.35 }]} />
      <TextInput
        value={row.expr}
        onChangeText={onChangeExpr}
        autoCapitalize="none"
        autoCorrect={false}
        spellCheck={false}
        accessibilityLabel={t("rich.graph_expr_a11y")}
        testID={inputId}
        placeholder="y = x^2"
        placeholderTextColor={theme.textSecondary}
        style={[
          styles.input,
          row.invalid && styles.inputInvalid,
          !row.visible && styles.dim,
        ]}
      />
      {row.locked ? null : (
        <>
          <Pressable
            onPress={onToggle}
            testID={`graph-hide-${row.id}`}
            accessibilityRole="button"
            accessibilityLabel={row.visible ? t("rich.graph_hide_series") : t("rich.graph_show_series")}
            hitSlop={8}
            style={styles.iconBtn}
          >
            <Icon
              name={row.visible ? "eye-outline" : "eye-off-outline"}
              size={18}
              color={theme.textSecondary}
            />
          </Pressable>
          <Pressable
            onPress={onRemove}
            testID={`graph-remove-${row.id}`}
            accessibilityRole="button"
            accessibilityLabel={t("rich.graph_remove_series")}
            hitSlop={8}
            style={styles.iconBtn}
          >
            <Icon name="trash-outline" size={18} color={theme.textSecondary} />
          </Pressable>
        </>
      )}
    </View>
  );
}

const makeExplorerStyles = (theme: Theme) =>
  StyleSheet.create({
    card: {
      alignSelf: "stretch",
      alignItems: "stretch",
      width: "100%",
    },
    plotPress: {
      position: "relative",
      alignSelf: "stretch",
    },
    expandBadge: {
      position: "absolute",
      bottom: 8,
      right: 8,
      width: 32,
      height: 32,
      borderRadius: 16,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      backgroundColor: theme.bg,
      alignItems: "center",
      justifyContent: "center",
    },
    modalRoot: {
      flex: 1,
    },
    modalSheet: {
      flex: 1,
    },
    modalToolbar: {
      alignSelf: "stretch",
    },
    handle: {
      alignSelf: "center",
      width: 36,
      height: 4,
      borderRadius: 2,
      backgroundColor: theme.border,
      marginTop: Space.xs,
      marginBottom: Space.xxs,
    },
    closeBtn: {
      alignSelf: "flex-start",
      padding: Space.xs,
      marginLeft: Space.xs,
    },
    modalPlot: {
      flex: 1,
      minHeight: MODAL_PLOT_MIN,
    },
    skiaLoading: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
    },
    modalList: {
      flexGrow: 0,
      flexShrink: 1,
      maxHeight: MODAL_LIST_MAX,
    },
    modalListContent: {
      paddingHorizontal: Space.md,
      paddingTop: Space.xs,
      paddingBottom: Space.sm,
      gap: 8,
    },
    list: {
      alignSelf: "stretch",
      marginTop: 8,
      gap: 8,
    },
    row: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
    },
    swatch: {
      width: 8,
      height: 8,
      borderRadius: 4,
    },
    input: {
      flex: 1,
      margin: 0,
      paddingVertical: 2,
      fontFamily: CODE_FONT,
      fontSize: 15,
      fontWeight: "600",
      color: theme.text,
    },
    inputInvalid: {
      color: theme.danger,
    },
    dim: {
      opacity: 0.4,
    },
    iconBtn: {
      padding: 4,
    },
    addBtn: {
      flexDirection: "row",
      alignItems: "center",
      gap: 4,
      alignSelf: "flex-start",
      paddingVertical: 4,
    },
    addText: {
      fontSize: 14,
      fontWeight: "600",
      color: theme.primary,
    },
  });
