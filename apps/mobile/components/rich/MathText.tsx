import { useMemo, type ReactNode } from "react";
import { ScrollView, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import Svg, { Path } from "react-native-svg";

import { MATH_FONT, MATH_SYMBOL_FONT, MATH_VARIABLE_FONT, mathFace } from "@/lib/fonts";
import {
  BODY_LINE_AT_16,
  FRAC_LINE_AT_16,
  FRAC_SIZE_RATIO,
  inlineMathNeedsScroll,
  layoutMath,
  radicalStroke,
  SCRIPT_RATIO,
  splitOperatorPads,
  SQRT_LINE_AT_16,
  type MathLayout,
} from "@/lib/math/layout";
import { fixImplicitExponents } from "@/lib/math/normalizeImplicit";
import {
  AMS_ONLY_CHARS,
  BLACKBOARD_LATIN,
  MATH_NOT_GLYPH,
  NEGATED_RELATION,
  NOT_ADVANCE_EM,
  NORM_ADVANCE_EM,
  primeRun,
} from "@/lib/math/glyphs";
import {
  attachScripts,
  parseSimpleLatex,
  readableLatexFallback,
  type MathSegment,
} from "@/lib/math/text";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  latex: string;
  textColor?: string;
  /** Tight line box — for hosts that draw their own rule above the content
   * (the composer radicand slot), where base leading pushes ink off the bar. */
  compact?: boolean;
  /** Used by editable root degrees; layout scales with the actual text size. */
  fontSize?: number;
  /** Markdown's View host can constrain tall runs and scroll their full width.
   * Leave this off in editable math slots and hosts with their own viewport. */
  scrollOverflow?: boolean;
};

type Styles = ReturnType<typeof makeStyles>;

/** Named operators are words, not products of variables, so they stay
 * upright in the same way KaTeX renders `sin`, `log`, and `mod`. */
const UPRIGHT_MATH_WORDS = new Set([
  "arccos", "arcsin", "arctan", "cos", "cosh", "cot", "csc", "det",
  "exp", "gcd", "if", "lim", "ln", "log", "max", "min", "mod",
  "otherwise", "rank", "sec", "sin", "sinh", "tan", "tanh", "where",
]);

const MATH_LETTER_RUN = /[A-Za-z\u0370-\u03ff]+/g;

function isUprightWord(value: string): boolean {
  return UPRIGHT_MATH_WORDS.has(value.toLowerCase());
}

function renderNonVariableRun(
  value: string,
  key: string,
  glyphStyle: object,
  metrics: { em: number; fontScale: number },
): ReactNode[] {
  return Array.from(value).map((ch, i) => renderMathGlyph(ch, `${key}-g${i}`, glyphStyle, metrics));
}

function renderMathGlyph(
  ch: string,
  key: string,
  glyphStyle: object,
  metrics: { em: number; fontScale: number },
): ReactNode {
  const negated = NEGATED_RELATION[ch];
  if (negated) {
    const shift = NOT_ADVANCE_EM * metrics.em * metrics.fontScale;
    return (
      <Text key={key} testID="math-negated" accessibilityLabel={ch}>
        <Text style={{ letterSpacing: -shift }}>{MATH_NOT_GLYPH}</Text>
        {negated.base}
      </Text>
    );
  }
  const blackboard = BLACKBOARD_LATIN[ch];
  if (blackboard) {
    return (
      <Text key={key} testID="math-blackboard" style={glyphStyle}>
        {blackboard}
      </Text>
    );
  }
  if (AMS_ONLY_CHARS.has(ch)) {
    return (
      <Text key={key} style={glyphStyle}>
        {ch}
      </Text>
    );
  }
  const primes = primeRun(ch);
  if (primes) return primes;
  if (ch === "-") return "−";
  if (ch === "·") return "⋅";
  if (ch === "‖") {
    const pull = (0.8 - NORM_ADVANCE_EM) * metrics.em * metrics.fontScale;
    return (
      <Text key={key} testID="math-norm" style={{ letterSpacing: -pull / 2 }}>
        ||
      </Text>
    );
  }
  return ch;
}

function renderMathRun(
  value: string,
  key: string,
  textStyle: object,
  glyphStyle: object,
  variableStyle: object,
  testID?: string,
  pad?: { em: number; fontScale: number; leadingAtom: boolean; space?: boolean },
): ReactNode {
  const pieces = pad && pad.space !== false
    ? splitOperatorPads(value, pad.leadingAtom)
    : [{ text: value, leftEm: 0, rightEm: 0 }];
  const runs = pieces.map((piece, pieceIndex) => {
    const pieceKey = pieces.length === 1 ? key : `${key}-p${pieceIndex}`;
    const children: ReactNode[] = [];
    let cursor = 0;
    let variableIndex = 0;
    for (const match of piece.text.matchAll(MATH_LETTER_RUN)) {
      const start = match.index ?? 0;
      if (start > cursor) {
        children.push(
          ...renderNonVariableRun(
            piece.text.slice(cursor, start),
            `${pieceKey}-t${cursor}`,
            glyphStyle,
            { em: pad?.em ?? 16, fontScale: pad?.fontScale ?? 1 },
          ),
        );
      }
      const word = match[0];
      children.push(
        isUprightWord(word) ? word : (
          <Text
            key={`${pieceKey}-v${variableIndex}`}
            testID="math-variable"
            style={[textStyle, variableStyle]}
          >
            {word}
          </Text>
        ),
      );
      variableIndex += 1;
      cursor = start + word.length;
    }
    if (cursor < piece.text.length) {
      children.push(
        ...renderNonVariableRun(
          piece.text.slice(cursor),
          `${pieceKey}-t${cursor}`,
          glyphStyle,
          { em: pad?.em ?? 16, fontScale: pad?.fontScale ?? 1 },
        ),
      );
    }
    // Padding, not margin: nested Text on iOS ignores margin, so the
    // measured operator space would never appear.
    const margin = pad
      ? {
          paddingLeft: piece.leftEm * pad.em * pad.fontScale,
          paddingRight: piece.rightEm * pad.em * pad.fontScale,
        }
      : null;
    return (
      <Text key={pieceKey} style={[textStyle, margin]} testID={pieces.length === 1 ? testID : undefined}>
        {children}
      </Text>
    );
  });
  if (runs.length === 1) return runs[0];
  return runs;
}

function isFractionalScript(seg: MathSegment): boolean {
  if (seg.type !== "sup") return false;
  const slash = seg.value.indexOf("/");
  return slash > 0 && slash < seg.value.length - 1 && !seg.value.includes(" ");
}

function hasRaisedScript(segments: MathSegment[]): boolean {
  return segments.some((seg) => seg.type === "sup" || seg.type === "sub");
}

function hasStackedMath(segments: MathSegment[]): boolean {
  return segments.some((seg) => (
    seg.type === "frac" || seg.type === "sqrt" || seg.type === "cancel"
    || seg.type === "accent" || isFractionalScript(seg)
  ));
}

function hasTallMath(segments: MathSegment[]): boolean {
  // A lone `x^2` used to stay inside Text, and iOS ignores translateY there,
  // so the exponent sat on the baseline and read as x2. The shift only
  // sticks when the script is a child of a View, which is how the fraction
  // in a divide step already draws it.
  return hasStackedMath(segments) || hasRaisedScript(segments);
}

type RenderCtx = {
  styles: Styles;
  color: string;
  inFrac?: boolean;
  textStyle?: object;
  /** Device font scale only. Layout pixels are already at `em`. */
  fontScale: number;
  em: number;
};

function runStyle(ctx: RenderCtx): object {
  if (ctx.textStyle) return ctx.textStyle;
  return ctx.inFrac ? ctx.styles.fracPart : ctx.styles.base;
}

/** Face at `em`, used when a script is smaller than the stylesheet's 16px sizes. */
function faceAt(ctx: RenderCtx, em: number, lineOverFont: number): object {
  return {
    ...mathFace(MATH_FONT),
    fontSize: em,
    lineHeight: em * lineOverFont,
    color: ctx.color,
  };
}

function renderFracSide(
  segments: MathSegment[],
  layout: MathLayout | undefined,
  keyPrefix: string,
  ctx: RenderCtx,
): ReactNode {
  const { styles } = ctx;
  const sideEm = ctx.inFrac ? ctx.em : ctx.em * FRAC_SIZE_RATIO;
  const sized = ctx.textStyle
    ? { ...faceAt(ctx, sideEm, FRAC_LINE_AT_16 / 14), textAlign: "center" as const }
    : null;
  const sideCtx = {
    ...ctx,
    inFrac: true,
    em: sideEm,
    textStyle: sized ?? ctx.textStyle,
  };
  // Nested fraction OR a radical: keep real Views. Flattening a radicand
  // to combining overlines made the minus look like `=` and inflated the bar.
  if (hasTallMath(segments)) {
    return (
      <View style={styles.fracSideRow}>
        {renderSegments(segments, layout?.children ?? [], keyPrefix, sideCtx)}
      </View>
    );
  }
  return (
    <Text style={sized ?? styles.fracPart}>
      {renderSegments(segments, layout?.children ?? [], keyPrefix, sideCtx)}
    </Text>
  );
}

/**
 * Radicand keeps the surrounding text size. Reusing the fraction-sized side
 * renderer made `\sqrt{8}` read as a subscript, and its plain-text flattening
 * leaked scripts as literal `8^3`. Nested stacks still take the View path (a
 * View cannot live in that Text).
 */
function renderRadicand(
  segments: MathSegment[],
  layout: MathLayout | undefined,
  keyPrefix: string,
  ctx: RenderCtx,
): ReactNode {
  const { styles } = ctx;
  const nested = hasTallMath(segments);
  const bodyStyle = ctx.textStyle
    ? faceAt(ctx, ctx.em, (ctx.inFrac ? FRAC_LINE_AT_16 / 14 : SQRT_LINE_AT_16 / 16))
    : ctx.inFrac
      ? styles.fracPart
      : styles.sqrtBody;
  const bodyCtx = { ...ctx, textStyle: bodyStyle };
  if (nested) {
    return (
      <View style={styles.fracSideRow}>
        {renderSegments(segments, layout?.children ?? [], keyPrefix, bodyCtx)}
      </View>
    );
  }
  return (
    <Text style={bodyStyle}>
      {renderSegments(segments, layout?.children ?? [], keyPrefix, bodyCtx)}
    </Text>
  );
}

function scriptTextStyle(node: MathLayout | undefined, ctx: RenderCtx, placed = false): object {
  const fontSize = node?.fontSize ?? ctx.em * SCRIPT_RATIO;
  const shift = placed
    ? 0
    : ((node?.raise ?? 0) > 0 ? -(node?.raise ?? 0) : (node?.drop ?? 0)) * ctx.fontScale;
  return {
    ...mathFace(MATH_FONT),
    fontSize,
    lineHeight: node?.lineHeight ?? fontSize * 1.15,
    color: ctx.color,
    transform: [{ translateY: shift }],
  };
}

function scaled(px: number, fontScale: number): number {
  return px * fontScale;
}

function renderAccentMark(node: MathLayout, ctx: RenderCtx): ReactNode {
  const rule = scaled(node.ruleWidth ?? node.inkWidth, ctx.fontScale);
  const thick = Math.max(1, scaled(ctx.em * 0.06, ctx.fontScale));
  const kind = node.accentKind;
  if (kind === "dot" || kind === "ddot") {
    const dot = (
      <View
        testID="math-accent-rule"
        style={{ width: thick, height: thick, borderRadius: thick, backgroundColor: ctx.color }}
      />
    );
    return (
      <View style={{ flexDirection: "row", gap: thick, alignSelf: "center" }}>
        {dot}
        {kind === "ddot" ? dot : null}
      </View>
    );
  }
  if (kind === "hat" || kind === "vec" || kind === "vecLeft" || kind === "tilde") {
    const w = rule;
    const h = scaled(ctx.em * 0.18, ctx.fontScale);
    const d = kind === "hat"
      ? `M 0 ${h} L ${w / 2} 0 L ${w} ${h}`
      : kind === "tilde"
        ? `M 0 ${h * 0.7} Q ${w * 0.25} 0 ${w * 0.5} ${h * 0.55} T ${w} ${h * 0.2}`
        : kind === "vecLeft"
          ? `M ${w} ${h * 0.5} L 0 ${h * 0.5} M 0 ${h * 0.5} L ${w * 0.28} 0 M 0 ${h * 0.5} L ${w * 0.28} ${h}`
          : `M 0 ${h * 0.5} L ${w} ${h * 0.5} M ${w} ${h * 0.5} L ${w * 0.72} 0 M ${w} ${h * 0.5} L ${w * 0.72} ${h}`;
    return (
      <Svg testID="math-accent-rule" width={w} height={h} viewBox={`0 0 ${Math.max(w, 1)} ${Math.max(h, 1)}`}>
        <Path d={d} fill="none" stroke={ctx.color} strokeWidth={Math.max(1, thick * 0.8)} strokeLinecap="round" />
      </Svg>
    );
  }
  return (
    <View
      testID="math-accent-rule"
      style={{ width: rule, height: thick, backgroundColor: ctx.color, alignSelf: "center" }}
    />
  );
}

function renderScriptColumn(
  sup: Extract<MathSegment, { type: "sup" }>,
  sub: Extract<MathSegment, { type: "sub" }>,
  node: MathLayout | undefined,
  key: string,
  ctx: RenderCtx,
): ReactNode {
  const pad = { em: ctx.em, fontScale: ctx.fontScale, leadingAtom: true };
  return (
    <View
      key={key}
      testID="math-script-column"
      style={{
        width: scaled(node?.width ?? 0, ctx.fontScale),
        height: scaled(node?.height ?? 0, ctx.fontScale),
        paddingTop: scaled(node?.padTop ?? 0, ctx.fontScale),
        paddingBottom: scaled(node?.padBottom ?? 0, ctx.fontScale),
        alignItems: "center",
        justifyContent: "space-between",
      }}
    >
      {renderOneSegment(sup, node?.children[0], `${key}-sup`, ctx, pad, true)}
      {renderOneSegment(sub, node?.children[1], `${key}-sub`, ctx, pad, true)}
    </View>
  );
}

function renderSegments(
  segments: MathSegment[],
  layouts: MathLayout[],
  keyPrefix: string,
  ctx: RenderCtx,
): ReactNode[] {
  const nodes: ReactNode[] = [];
  let leadingAtom = false;
  let layoutIndex = 0;
  for (const atom of attachScripts(segments)) {
    const key = `${keyPrefix}-${atom.index}`;
    const node = layouts[layoutIndex];
    layoutIndex += 1;
    const pad = { em: ctx.em, fontScale: ctx.fontScale, leadingAtom };
    leadingAtom = true;
    const rendered = renderOneSegment(atom.segment, node, key, ctx, pad, false);
    if (atom.sup && atom.sub) {
      const column = layouts[layoutIndex];
      layoutIndex += 1;
      nodes.push(
        <View key={key} style={{ flexDirection: "row", alignItems: "center" }}>
          {rendered}
          {renderScriptColumn(atom.sup, atom.sub, column, `${key}-col`, ctx)}
        </View>,
      );
    } else if (rendered != null) {
      nodes.push(rendered);
    }
  }
  return nodes;
}

function renderOneSegment(
  seg: MathSegment,
  node: MathLayout | undefined,
  key: string,
  ctx: RenderCtx,
  pad: { em: number; fontScale: number; leadingAtom: boolean },
  placed: boolean,
): ReactNode {
  const { styles } = ctx;
  if (seg.type === "sup" || seg.type === "sub") {
      if (seg.body) {
        const scriptEm = node?.fontSize ?? ctx.em * SCRIPT_RATIO;
        const shift = placed
          ? 0
          : ((node?.raise ?? 0) > 0 ? -(node?.raise ?? 0) : (node?.drop ?? 0)) * ctx.fontScale;
        const inner = node?.children[0];
        return (
          <View
            key={key}
            testID="math-script"
            style={{
              width: scaled(node?.width ?? 0, ctx.fontScale),
              height: scaled(node?.height ?? 0, ctx.fontScale),
              paddingTop: scaled(inner?.padTop ?? 0, ctx.fontScale),
              paddingBottom: scaled(inner?.padBottom ?? 0, ctx.fontScale),
              transform: [{ translateY: shift }],
            }}
          >
            {renderSegments(seg.body, inner?.children ?? [], `${key}-b`, {
              ...ctx,
              em: scriptEm,
              textStyle: faceAt(ctx, scriptEm, 1.15),
            })}
          </View>
        );
      }
      if (seg.type === "sup" && isFractionalScript(seg)) {
        const slash = seg.value.indexOf("/");
        const scriptSize = node?.fontSize ?? ctx.em * SCRIPT_RATIO;
        const raise = node?.raise ?? ctx.em * 0.42;
        const scriptStyle = {
          ...mathFace(MATH_FONT),
          fontSize: scriptSize,
          lineHeight: scriptSize * 1.1,
          color: ctx.color,
        };
        return (
          <View
            key={key}
            testID="math-fractional-sup"
            style={{
              width: scaled(node?.width ?? scriptSize * 2, ctx.fontScale),
              height: scaled(node?.height ?? scriptSize * 2, ctx.fontScale),
              paddingBottom: scaled(raise, ctx.fontScale),
              alignItems: "center",
              justifyContent: "flex-start",
            }}
          >
            {renderMathRun(
              seg.value.slice(0, slash),
              `${key}-sn`,
              scriptStyle,
              styles.glyph,
              styles.variable,
              undefined,
              { em: scriptSize, fontScale: ctx.fontScale, leadingAtom: false, space: false },
            )}
            <View
              testID="math-script-bar"
              style={[styles.vinculum, { alignSelf: "stretch", marginVertical: 0 }]}
            />
            {renderMathRun(
              seg.value.slice(slash + 1),
              `${key}-sd`,
              scriptStyle,
              styles.glyph,
              styles.variable,
              undefined,
              { em: scriptSize, fontScale: ctx.fontScale, leadingAtom: false, space: false },
            )}
          </View>
        );
      }
      return renderMathRun(
        seg.value,
        key,
        scriptTextStyle(node, ctx, placed),
        styles.glyph,
        styles.variable,
        "math-script",
        {
          em: node?.fontSize ?? ctx.em * SCRIPT_RATIO,
          fontScale: ctx.fontScale,
          leadingAtom: false,
          space: false,
        },
      );
    }
    if (seg.type === "frac") {
      return (
        <View
          key={key}
          style={[styles.fracStack, {
            width: scaled(node?.width ?? 0, ctx.fontScale),
            height: scaled(node?.height ?? 0, ctx.fontScale),
            marginHorizontal: scaled((node?.outer ?? 0) / 2, ctx.fontScale),
            paddingTop: scaled(node?.padTop ?? 0, ctx.fontScale),
            paddingBottom: scaled(node?.padBottom ?? 0, ctx.fontScale),
          }]}
          testID="math-frac"
          collapsable={false}
        >
          {renderFracSide(seg.num, node?.children[0], `${key}-n`, ctx)}
          <View
            style={[styles.vinculum, { height: Math.max(1, ctx.fontScale), marginVertical: 0 }]}
            testID="math-vinculum"
          />
          {renderFracSide(seg.den, node?.children[1], `${key}-d`, ctx)}
        </View>
      );
    }
    if (seg.type === "sqrt") {
      if (!node) return <View key={key} testID="math-sqrt" />;
      const stroke = radicalStroke(node);
      const width = scaled(node.width, ctx.fontScale);
      const height = scaled(node.height, ctx.fontScale);
      const padLeft = node.padLeft ?? 0;
      const padRight = Math.max(0, node.outer - padLeft);
      return (
        <View
          key={key}
          style={[styles.sqrtRow, {
            width,
            height,
            marginLeft: scaled(padLeft, ctx.fontScale),
            marginRight: scaled(padRight, ctx.fontScale),
          }]}
          testID="math-sqrt"
          collapsable={false}
        >
          <Svg
            testID="math-radical-glyph"
            width={width}
            height={height}
            viewBox={`0 0 ${node.width} ${node.height}`}
            style={styles.radicalGlyph}
            pointerEvents="none"
            accessible={false}
          >
            <Path
              d={stroke.d}
              fill="none"
              stroke={ctx.color}
              strokeWidth={Math.max(0.9, (node.em ?? ctx.em) * 0.075)}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </Svg>
          {seg.index && node.index ? (
            <View
              testID="math-sqrt-index"
              style={{
                position: "absolute",
                left: scaled(node.index.left, ctx.fontScale),
                top: scaled(node.index.top, ctx.fontScale),
                width: scaled(node.index.width, ctx.fontScale),
                height: scaled(node.index.lineHeight, ctx.fontScale),
              }}
            >
              {renderSegments(seg.index, node.children[1]?.children ?? [], `${key}-i`, {
                ...ctx,
                em: node.index.fontSize,
                textStyle: faceAt(ctx, node.index.fontSize, 1.15),
              })}
            </View>
          ) : seg.degree && node.index ? (
            <Text
              style={[styles.sqrtIndex, {
                left: scaled(node.index.left, ctx.fontScale),
                top: scaled(node.index.top, ctx.fontScale),
                fontSize: node.index.fontSize,
                lineHeight: node.index.lineHeight,
                transform: [],
              }]}
            >
              {seg.degree}
            </Text>
          ) : null}
          <View
            style={[styles.sqrtRadicand, {
              marginLeft: scaled(node.lead ?? 0, ctx.fontScale),
              marginTop: scaled(node.bodyTop ?? 0, ctx.fontScale),
              width: scaled(node.children[0]?.width ?? node.bodyWidth ?? 0, ctx.fontScale),
              height: scaled(node.bodyHeight ?? 0, ctx.fontScale),
            }]}
            testID="math-sqrt-radicand"
          >
            {renderRadicand(seg.body, node.children[0], `${key}-b`, ctx)}
          </View>
        </View>
      );
    }
    if (seg.type === "accent") {
      if (!node) return <View key={key} testID="math-accent" />;
      const mark = renderAccentMark(node, ctx);
      const head = seg.kind === "underline" ? 0 : scaled(node.padTop ?? 0, ctx.fontScale);
      const foot = seg.kind === "underline" ? scaled(node.padBottom ?? 0, ctx.fontScale) : 0;
      return (
        <View
          key={key}
          testID="math-accent"
          collapsable={false}
          style={{
            width: scaled(node.width, ctx.fontScale),
            height: scaled(node.height, ctx.fontScale),
            alignItems: "center",
            justifyContent: "flex-start",
          }}
        >
          {seg.kind === "underline" ? null : mark}
          <View style={[styles.fracSideRow, { marginTop: head, marginBottom: foot }]}>
            {renderSegments(seg.body, node.children[0]?.children ?? [], `${key}-a`, ctx)}
          </View>
          {seg.kind === "underline" ? mark : null}
        </View>
      );
    }
    if (seg.type === "cancel") {
      return (
        <View key={key} testID="math-cancel" style={styles.cancelWrap} collapsable={false}>
          {renderSegments(seg.body, node?.children[0]?.children ?? [], `${key}-c`, ctx)}
          <View style={styles.cancelSlashHit} pointerEvents="none" accessible={false}>
            <View testID="math-cancel-slash" style={styles.cancelSlash} />
          </View>
        </View>
      );
    }
    if (seg.type === "upright") {
      return (
        <Text key={key} style={runStyle(ctx)} testID="math-upright-run">
          {renderNonVariableRun(seg.value, `${key}-u`, styles.glyph, { em: ctx.em, fontScale: ctx.fontScale })}
        </Text>
      );
    }
  if (seg.type !== "text") return null;
  return renderMathRun(seg.value, key, runStyle(ctx), styles.glyph, styles.variable, undefined, pad);
}

/** Native math: simple runs stay Text; stacked or raised structures own their bounds. */
export function MathText({ latex, textColor, compact = false, fontSize = 16, scrollOverflow = false }: Props) {
  const theme = useTheme();
  const color = textColor ?? theme.text;
  const { fontScale, width: windowWidth } = useWindowDimensions();
  const styles = useMemo(
    () => makeStyles(theme, textColor, compact, fontSize, fontScale),
    [theme, textColor, compact, fontSize, fontScale],
  );
  const segments = useMemo(
    () => parseSimpleLatex(fixImplicitExponents(latex.trim())),
    [latex],
  );
  const layout = useMemo(() => layoutMath(segments, fontSize), [segments, fontSize]);
  const tall = useMemo(() => hasTallMath(segments), [segments]);
  const stacked = useMemo(() => hasStackedMath(segments), [segments]);
  const ctx: RenderCtx = { styles, color, fontScale, em: fontSize };

  if (!latex.trim()) return null;

  const contentWidth = scaled(layout.width, fontScale);
  const contentHeight = scaled(layout.height, fontScale);
  const label = readableLatexFallback(latex);
  // A short power stays a View so the exponent can rise, without the
  // horizontal scroller that stacked fractions use even when they fit.
  const scroll = scrollOverflow && (stacked || inlineMathNeedsScroll(contentWidth, windowWidth));
  const runs = renderSegments(segments, layout.children, "m", ctx);

  // Stacked structures are a View root. Text > Text > View is what iOS lays
  // out as 0×0 and paints over the next line.
  if (tall) {
    // The measured height already includes the script raise. Padding keeps
    // that room inside the box so translateY lifts the exponent into it
    // instead of painting past the top, where a ScrollView would clip it.
    const padTop = scaled(layout.padTop ?? 0, fontScale);
    const padBottom = scaled(layout.padBottom ?? 0, fontScale);
    const content = (
      <View
        testID="math-text-tall"
        collapsable={false}
        style={[styles.tallRoot, {
          ...(scroll ? { minWidth: contentWidth } : { width: contentWidth }),
          height: contentHeight,
          ...(padTop > 0 ? { paddingTop: padTop } : null),
          ...(padBottom > 0 ? { paddingBottom: padBottom } : null),
        }]}
      >
        {runs}
      </View>
    );
    if (!scroll) return content;
    // The viewport is the paragraph width. The formula keeps its measured
    // width and scrolls; it is not shrunk to fit.
    return (
      <ScrollView
        testID="math-text-scroll"
        horizontal
        nestedScrollEnabled
        directionalLockEnabled
        showsHorizontalScrollIndicator
        bounces={false}
        contentInsetAdjustmentBehavior="never"
        accessible
        accessibilityRole="text"
        accessibilityLabel={label}
        style={[styles.inlineViewport, { height: contentHeight }]}
      >
        {content}
      </ScrollView>
    );
  }

  const lineHeight = Math.max(styles.base.lineHeight ?? 0, layout.height);
  if (scroll) {
    return (
      <ScrollView
        testID="math-text-scroll"
        horizontal
        nestedScrollEnabled
        directionalLockEnabled
        showsHorizontalScrollIndicator
        bounces={false}
        contentInsetAdjustmentBehavior="never"
        accessible
        accessibilityRole="text"
        accessibilityLabel={label}
        style={[styles.inlineViewport, { height: contentHeight }]}
      >
        <Text
          testID="math-text-wide"
          style={[styles.base, { lineHeight, minWidth: contentWidth, flexShrink: 0 }]}
        >
          {runs}
        </Text>
      </ScrollView>
    );
  }

  return (
    <Text style={[styles.base, { lineHeight }]}>
      {runs}
    </Text>
  );
}

const makeStyles = (theme: Theme, textColor?: string, compact = false, fontSize = 16, fontScale = 1) => {
  const color = textColor ?? theme.text;
  const scale = fontSize / 16;
  const layoutScale = scale * fontScale;
  return StyleSheet.create({
    base: {
      ...mathFace(MATH_FONT),
      fontSize,
      // Match body rhythm. 28 made nested `$m$` / `$y=mx+b$` Text
      // wrap onto its own line inside list items ("Slope (" / "m" / "): 3").
      lineHeight: (compact ? SQRT_LINE_AT_16 : BODY_LINE_AT_16) * scale,
      color,
    },
    glyph: mathFace(MATH_SYMBOL_FONT),
    variable: {
      ...mathFace(MATH_VARIABLE_FONT),
      color,
    },
    inlineViewport: {
      maxWidth: "100%",
      flexGrow: 0,
      flexShrink: 1,
    },
    tallRoot: {
      flexDirection: "row",
      alignItems: "center",
      flexShrink: 0,
      overflow: "visible",
    },
    fracStack: {
      alignItems: "center",
      alignSelf: "flex-start",
      justifyContent: "space-between",
      overflow: "visible",
      flexShrink: 0,
    },
    fracSideRow: {
      flexDirection: "row",
      alignItems: "center",
    },
    fracPart: {
      ...mathFace(MATH_FONT),
      fontSize: 14 * scale,
      lineHeight: FRAC_LINE_AT_16 * scale,
      color,
      textAlign: "center",
    },
    // One SVG path draws hook, rising stroke, and bar continuously. Its height
    // is derived from the radicand, so a stacked denominator stays inside it.
    sqrtRow: {
      flexDirection: "row",
      alignItems: "flex-start",
      overflow: "visible",
    },
    sqrtIndex: {
      position: "absolute",
      left: 0,
      top: 0,
      ...mathFace(MATH_FONT),
      fontSize: 12 * scale,
      lineHeight: 14 * scale,
      color,
    },
    sqrtBody: {
      ...mathFace(MATH_FONT),
      fontSize,
      lineHeight: SQRT_LINE_AT_16 * scale,
      color,
    },
    sqrtRadicand: {
      flexDirection: "row",
      alignItems: "flex-start",
      overflow: "visible",
    },
    radicalGlyph: {
      position: "absolute",
      left: 0,
      top: 0,
    },
    vinculum: {
      alignSelf: "stretch",
      height: 1,
      marginVertical: 0,
      backgroundColor: color,
    },
    cancelWrap: {
      alignItems: "center",
      justifyContent: "center",
    },
    cancelSlashHit: {
      ...StyleSheet.absoluteFill,
      alignItems: "center",
      justifyContent: "center",
    },
    cancelSlash: {
      width: "140%",
      height: 1.5 * layoutScale,
      backgroundColor: theme.danger,
      transform: [{ rotate: "-32deg" }],
    },
  });
};
