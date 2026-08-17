/**
 * MathSvgBlock — display-math block rendered natively via
 * `react-native-svg`'s `<SvgXml>` instead of a visible WebView. Asks the
 * shared `MathSvgBridge` for an SVG string (cached by LaTeX), then renders
 * it natively. Falls back to `MathFormulaWebView` (the current visible
 * WebView path) when the bridge is off/unready or the SVG fails.
 *
 * SPIKE — gated by `MATH_SVG_NATIVE_ENABLED`. When off, renders the
 * historical `MathFormulaWebView` so production behavior is unchanged.
 */

import React, { useEffect, useMemo, useState } from "react";
import { StyleSheet, View } from "react-native";
import { SvgXml } from "react-native-svg";

import { MathFormulaWebView } from "@/components/rich/MathFormulaWebView";
import { MATH_SVG_NATIVE_ENABLED, requestMathSvg } from "@/lib/mathSvgBridge";
import { useTheme } from "@/lib/theme";

type Props = {
  latex: string;
  textColor?: string;
};

export const MathSvgBlock = React.memo(function MathSvgBlock({ latex, textColor }: Props) {
  const theme = useTheme();
  const trimmed = latex.trim();
  const [svg, setSvg] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!MATH_SVG_NATIVE_ENABLED) return;
    let cancelled = false;
    setFailed(false);
    setSvg(null);
    requestMathSvg(trimmed)
      .then((out) => {
        if (!cancelled) setSvg(out);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [trimmed]);

  const fallback = useMemo(
    () => (
      <MathFormulaWebView
        latex={trimmed}
        displayMode
        minHeight={48}
        textColor={textColor ?? theme.text}
        bgColor="transparent"
      />
    ),
    [trimmed, textColor, theme.text],
  );

  if (!MATH_SVG_NATIVE_ENABLED || failed) return fallback;

  if (svg == null) {
    // Reserve space — never flash raw LaTeX. Use a stable height estimate.
    return <View style={[styles.reserve, { backgroundColor: "transparent" }]} />;
  }

  return (
    <View style={styles.wrap}>
      <SvgXml xml={svg} width="100%" height={undefined} />
    </View>
  );
});

const styles = StyleSheet.create({
  wrap: {
    marginVertical: 8,
    alignSelf: "stretch",
    alignItems: "center",
  },
  reserve: {
    marginVertical: 8,
    alignSelf: "stretch",
    minHeight: 48,
  },
});
