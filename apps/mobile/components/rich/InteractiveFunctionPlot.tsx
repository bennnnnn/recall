import { useId, useMemo, useState } from "react";
import {
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from "react-native";
import { GestureDetector, GestureHandlerRootView } from "react-native-gesture-handler";
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
import { CODE_FONT } from "@/lib/fonts";
import { formatGraphExpr, type GraphSpec } from "@/lib/graphBlock";
import { defaultInteractiveBounds } from "@/lib/graphViewport";
import { IconSize } from "@/lib/icons";
import { Theme } from "@/lib/theme";

const CHART_HEIGHT = 220;

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
  const cardAspect = (chartWidth - GRAPH_AXIS_PAD * 2) / (CHART_HEIGHT - GRAPH_AXIS_PAD * 2 || 1);
  const cardBounds = useMemo(() => defaultInteractiveBounds(cardAspect), [cardAspect]);
  const cardDrawn = useMemo(
    () => series.map((row, i) => drawGraphSeries(row, palette[i % palette.length], variable, cardBounds)),
    [cardBounds, palette, series, variable],
  );
  const modalWidth = Math.max(1, screenW - 24);
  const modalHeight = Math.max(240, screenH - insets.top - insets.bottom - 200);
  const viewport = useGraphViewport({ width: modalWidth, height: modalHeight, pad: GRAPH_AXIS_PAD });
  const modalDrawn = useMemo(
    () =>
      series.map((row, i) =>
        drawGraphSeries(row, palette[i % palette.length], variable, viewport.bounds),
      ),
    [palette, series, variable, viewport.bounds],
  );
  const customTitle =
    spec.title != null && spec.title.trim() !== "" && spec.title.trim() !== spec.expr
      ? formatGraphExpr(spec.title)
      : null;
  const seriesEditor = (rows: DrawnSeries[]) =>
    editable ? (
      <View style={explorerStyles.list}>
        {rows.map((row) => (
          <SeriesRow
            key={row.id}
            row={row}
            theme={theme}
            styles={explorerStyles}
            onChangeExpr={(text) => setExpr(row.id, text)}
            onToggle={() => toggleVisible(row.id)}
            onRemove={() => removeSeries(row.id)}
          />
        ))}
        {canAdd ? (
          <Pressable
            onPress={addSeries}
            testID="graph-add-function"
            accessibilityRole="button"
            accessibilityLabel={t("rich.graph_add_function")}
            style={explorerStyles.addBtn}
          >
            <Icon name="add-outline" size={16} color={theme.primary} />
            <Text style={explorerStyles.addText}>{t("rich.graph_add_function")}</Text>
          </Pressable>
        ) : null}
      </View>
    ) : null;

  return (
    <View style={styles.wrap}>
      {customTitle ? <Text style={styles.title}>{customTitle}</Text> : null}
      {isVerticalLine ? (
        <Text style={styles.title}>{formatGraphExpr(spec.title ?? spec.expr)}</Text>
      ) : null}
      <Pressable
        onPress={() => setOpen(true)}
        testID="graph-expand"
        accessibilityRole="button"
        accessibilityLabel={t("rich.expand")}
        style={[explorerStyles.plotPress, { width: chartWidth, height: CHART_HEIGHT }]}
      >
        <GraphCanvas
          spec={spec}
          theme={theme}
          clipId={cardClipId}
          width={chartWidth}
          height={CHART_HEIGHT}
          bounds={cardBounds}
          drawn={cardDrawn}
          verticalX={verticalX}
        />
        <View style={explorerStyles.expandBadge} pointerEvents="none">
          <Icon name="expand-outline" size={16} color={theme.textSecondary} />
        </View>
      </Pressable>
      {open ? null : seriesEditor(cardDrawn)}
      <Modal
        visible={open}
        animationType="slide"
        presentationStyle="fullScreen"
        onRequestClose={() => setOpen(false)}
      >
        {open ? (
          <GestureHandlerRootView
            style={[
              explorerStyles.modalRoot,
              {
                backgroundColor: theme.bg,
                paddingTop: insets.top,
                paddingBottom: insets.bottom,
              },
            ]}
          >
            <KeyboardAvoidingView
              style={explorerStyles.modalRoot}
              behavior={Platform.OS === "ios" ? "padding" : undefined}
            >
              <View style={explorerStyles.modalToolbar}>
                <Pressable
                  onPress={() => setOpen(false)}
                  testID="graph-close"
                  accessibilityRole="button"
                  accessibilityLabel={t("preview.close")}
                  hitSlop={8}
                  style={explorerStyles.iconBtn}
                >
                  <Icon name="close-outline" size={IconSize.lg} color={theme.text} />
                </Pressable>
              </View>
              <GestureDetector gesture={viewport.gesture}>
                <View
                  collapsable={false}
                  pointerEvents="box-only"
                  accessible
                  accessibilityLabel={t("rich.graph_plot_a11y")}
                  style={{ width: modalWidth, height: modalHeight }}
                >
                  <GraphCanvas
                    spec={spec}
                    theme={theme}
                    clipId={modalClipId}
                    width={modalWidth}
                    height={modalHeight}
                    bounds={viewport.bounds}
                    drawn={modalDrawn}
                    verticalX={verticalX}
                  />
                </View>
              </GestureDetector>
              {seriesEditor(modalDrawn)}
            </KeyboardAvoidingView>
          </GestureHandlerRootView>
        ) : null}
      </Modal>
    </View>
  );
}

function hasCurve2(spec: GraphSpec): boolean {
  return spec.type === "function" && !!spec.expr2 && !!spec.points2?.length;
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
      <Text style={[styles.prefix, !row.visible && styles.dim]}>y = </Text>
      <TextInput
        value={row.expr}
        onChangeText={onChangeExpr}
        autoCapitalize="none"
        autoCorrect={false}
        spellCheck={false}
        accessibilityLabel={t("rich.graph_expr_a11y")}
        testID={inputId}
        placeholder="x^2"
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
            <Icon name="close-outline" size={18} color={theme.textSecondary} />
          </Pressable>
        </>
      )}
    </View>
  );
}

const makeExplorerStyles = (theme: Theme) =>
  StyleSheet.create({
    plotPress: {
      position: "relative",
    },
    expandBadge: {
      position: "absolute",
      top: 8,
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
    modalToolbar: {
      flexDirection: "row",
      alignItems: "center",
      paddingHorizontal: 8,
      paddingVertical: 4,
    },
    list: {
      alignSelf: "stretch",
      marginTop: 8,
      gap: 8,
      paddingHorizontal: 16,
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
    prefix: {
      fontSize: 15,
      fontWeight: "600",
      color: theme.text,
    },
    input: {
      flex: 1,
      margin: 0,
      paddingVertical: 2,
      fontFamily: CODE_FONT,
      fontSize: 15,
      fontWeight: "600",
      color: theme.text,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: theme.border,
    },
    inputInvalid: {
      color: theme.danger,
      borderBottomColor: theme.danger,
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
