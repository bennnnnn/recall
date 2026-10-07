import { memo, useMemo, useRef } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { MathComposerCaret } from "@/components/chat/MathComposerCaret";
import { MathText } from "@/components/rich/MathText";
import { splitInlineMath } from "@/lib/markdown/preprocess";
import { textLooksLikeMath } from "@/lib/math/composerIntent";
import { isMostlyProsePaste } from "@/lib/math/pasteNormalize";
import {
  caretAfterExpression,
  caretBeforeExpression,
  findDraftNodes,
  shiftDraftNodes,
  type DraftNode,
} from "@/lib/math/draftSlots";
import { healDroppedCommandSlash } from "@/lib/math/healMathSource";
import { innermostSlot, type LatexGroup } from "@/lib/math/keyboardSymbols";
import { latexNeedsTallLine, MATH_TALL_LINE_HEIGHT } from "@/lib/math/text";
import { Theme, useTheme } from "@/lib/theme";

export const MATH_DRAFT_PREVIEW_HEIGHT = 48;

/**
 * True when the composer draft should show the live math preview.
 * Shows when the input contains `$` (explicit math delimiters) OR when it
 * looks like math content (LaTeX commands, math symbols, bare equations)
 * even without `$` — so typing `√9` or `x^2 = 4` shows the preview without
 * requiring the user to manually wrap in `$...$`.
 *
 * Note: `UserMessageContent` uses its own check (only `$`) for sent messages;
 * this broader check is for the live composer draft only.
 */
export function draftShowsMathPreview(input: string): boolean {
  const s = input.trim();
  if (s.length === 0) return false;
  if (isMostlyProsePaste(s)) return false;
  if (input.includes("$")) return true;
  return textLooksLikeMath(input);
}

/**
 * True when a *sent* user message should render via `MathDraftPreview`.
 * Unlike the composer, sent messages only use the preview when the user
 * explicitly wrapped math in `$...$` — bare equations in sent messages
 * render through the normal markdown path (which handles implicit math).
 *
 * Multi-line / display-math pastes (`\[...\]`, `$$...$$`) must not use the
 * composer preview: wrapping them in one `$` row left a tall empty bubble.
 */
export function sentMessageShowsMathPreview(input: string): boolean {
  const s = input.trim();
  if (!s.includes("$") || s.length === 0) return false;
  if (s.includes("\n")) return false;
  if (s.includes("\\[") || s.includes("\\]") || s.includes("$$")) return false;
  if (s.length > 160) return false;
  return true;
}

type ScriptNode = Extract<DraftNode, { kind: "script" }>;

/** ∑, ∏, and lim carry their scripts above and below. Everything else keeps them beside the base. */
const LIMIT_BASE = /\\(?:sum|prod|lim)\s*$/;

function isLimitBase(input: string, node: DraftNode): boolean {
  return node.kind === "text" && LIMIT_BASE.test(input.slice(node.start, node.end).replace(/\$/g, ""));
}

/** A superscript or subscript belongs on the previous symbol, not as the next item in the row. */
function clusterDraftNodes(nodes: DraftNode[]): { node: DraftNode; scripts: ScriptNode[] }[] {
  const groups: { node: DraftNode; scripts: ScriptNode[] }[] = [];
  for (let i = 0; i < nodes.length; i += 1) {
    const node = nodes[i]!;
    if (node.kind === "script") {
      const prev = groups[groups.length - 1];
      if (prev) prev.scripts.push(node);
      else groups.push({ node, scripts: [] });
      continue;
    }
    const scripts: ScriptNode[] = [];
    while (nodes[i + 1]?.kind === "script") {
      scripts.push(nodes[i + 1] as ScriptNode);
      i += 1;
    }
    groups.push({ node, scripts });
  }
  return groups;
}

type Props = {
  input: string;
  caret?: number;
  onMoveCaret?: (pos: number) => void;
  /** Composer only. Sent bubbles must not show an insert caret. */
  showCaret?: boolean;
};

export const MathDraftPreview = memo(function MathDraftPreview({
  input,
  caret = 0,
  onMoveCaret,
  showCaret = true,
}: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  // When the input looks like math but has no `$` delimiters (e.g. "√9" or
  // "x^2 = 4"), wrap it so findDraftNodes/splitInlineMath treat it as math.
  const healed = useMemo(() => {
    const wrapped = input.includes("$") ? input : `$${input}$`;
    return healDroppedCommandSlash(wrapped, caret, caret);
  }, [input, caret]);
  const mathInput = healed.text;
  const viewCaret = healed.start;
  const nodes = useMemo(() => findDraftNodes(mathInput), [mathInput]);
  const parts = useMemo(() => splitInlineMath(mathInput), [mathInput]);
  const before = caretBeforeExpression(mathInput);
  const after = caretAfterExpression(mathInput);
  const tall = parts.some((p) => p.type === "math" && latexNeedsTallLine(p.value));
  if (!draftShowsMathPreview(input)) return null;
  const liveCaret = showCaret && viewCaret >= 0;
  const showBeforeCaret = liveCaret && viewCaret <= before && viewCaret < after;
  const showAfterCaret = liveCaret && viewCaret >= after;

  const pieces = clusterDraftNodes(nodes);
  const pieceCaret = liveCaret ? viewCaret : -1;
  return (
    <View style={[s.wrap, s.row, tall && { minHeight: MATH_TALL_LINE_HEIGHT }]} testID="math-draft-preview">
      <Pressable
        testID="math-slot-before"
        onPress={() => onMoveCaret?.(before)}
        style={s.edge}
        accessibilityRole="button"
      >
        {showBeforeCaret ? <MathComposerCaret testID="math-slot-before-caret" /> : null}
      </Pressable>
      {pieces.map((piece) => (
        <DraftAtom
          key={`${piece.node.kind}-${piece.node.start}`}
          piece={piece}
          input={mathInput}
          caret={pieceCaret}
          before={before}
          after={after}
          onMoveCaret={onMoveCaret}
        />
      ))}
      <Pressable
        testID="math-slot-after"
        onPress={() => onMoveCaret?.(after)}
        style={s.edge}
        accessibilityRole="button"
      >
        {showAfterCaret ? <MathComposerCaret testID="math-slot-after-caret" /> : null}
      </Pressable>
    </View>
  );
});

function DraftAtom({
  piece,
  input,
  caret,
  before,
  after,
  onMoveCaret,
}: {
  piece: { node: DraftNode; scripts: ScriptNode[] };
  input: string;
  caret: number;
  before: number;
  after: number;
  onMoveCaret?: (pos: number) => void;
}) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const limits = piece.scripts.length > 0 && isLimitBase(input, piece.node);
  const sup = piece.scripts.filter((node) => node.mark === "^");
  const sub = piece.scripts.filter((node) => node.mark === "_");
  const base = (
    <DraftPiece
      node={piece.node}
      input={input}
      caret={caret}
      before={before}
      after={after}
      onMoveCaret={onMoveCaret}
    />
  );
  if (!limits) {
    return (
      <View style={s.atom}>
        {base}
        {piece.scripts.length > 0 ? (
          <ScriptStack
            scripts={piece.scripts}
            input={input}
            caret={caret}
            before={before}
            after={after}
            onMoveCaret={onMoveCaret}
          />
        ) : null}
      </View>
    );
  }
  return (
    <View style={s.limitAtom}>
      <ScriptStack
        scripts={sup}
        input={input}
        caret={caret}
        before={before}
        after={after}
        onMoveCaret={onMoveCaret}
        place="over"
      />
      {base}
      <ScriptStack
        scripts={sub}
        input={input}
        caret={caret}
        before={before}
        after={after}
        onMoveCaret={onMoveCaret}
        place="over"
      />
    </View>
  );
}

function ScriptStack({
  scripts,
  input,
  caret,
  before,
  after,
  onMoveCaret,
  place = "side",
}: {
  scripts: ScriptNode[];
  input: string;
  caret: number;
  before: number;
  after: number;
  onMoveCaret?: (pos: number) => void;
  place?: "side" | "over";
}) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  if (scripts.length === 0) return null;
  const sup = scripts.filter((node) => node.mark === "^");
  const sub = scripts.filter((node) => node.mark === "_");
  const lift = place === "side" && sup.length > 0 && sub.length === 0;
  const drop = place === "side" && sub.length > 0 && sup.length === 0;
  return (
    <View style={[place === "side" ? s.scriptStack : s.scriptOver, lift && s.scriptLift, drop && s.scriptDrop]}>
      {[...sup, ...sub].map((node) => (
        <DraftPiece
          key={`${node.mark}-${node.start}`}
          node={node}
          input={input}
          caret={caret}
          before={before}
          after={after}
          onMoveCaret={onMoveCaret}
        />
      ))}
    </View>
  );
}

function DraftPiece({
  node,
  input,
  caret,
  before,
  after,
  onMoveCaret,
}: {
  node: DraftNode;
  input: string;
  caret: number;
  before: number;
  after: number;
  onMoveCaret?: (pos: number) => void;
}) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  if (node.kind === "text") {
    const display = input
      .slice(node.start, node.end)
      .replace(/\$/g, "")
      .replace(/[{}]/g, "");
    if (!display) return null;
    let start = node.start;
    if (input[start] === "$") start += 1;
    let end = node.end;
    if (input[end - 1] === "$") end -= 1;
    return (
      <Pressable
        testID="math-slot-text"
        onPress={(e) => {
          const x = e.nativeEvent.locationX;
          onMoveCaret?.(x < 8 ? start : end);
        }}
        style={s.textHit}
        accessibilityRole="button"
      >
        <View style={s.slotRow}>
          {caret === start && start > before ? (
            <MathComposerCaret testID="math-slot-text-caret-start" />
          ) : null}
          {/\\/.test(display) ? (
            <MathText latex={display} textColor={theme.text} />
          ) : (
            <Text style={s.prose}>{display}</Text>
          )}
          {caret === end && end < after ? <MathComposerCaret testID="math-slot-text-caret" /> : null}
        </View>
      </Pressable>
    );
  }

  if (node.kind === "frac") {
    return (
      <View style={s.frac} testID="math-frac">
        <EditSlot
          text={input}
          group={node.num}
          caret={caret}
          before={before}
          after={after}
          testID="math-slot-num"
          onMoveCaret={onMoveCaret}
        />
        <View style={s.vinculum} testID="math-vinculum" />
        <EditSlot
          text={input}
          group={node.den}
          caret={caret}
          before={before}
          after={after}
          testID="math-slot-den"
          onMoveCaret={onMoveCaret}
        />
      </View>
    );
  }

  if (node.kind === "sqrt") {
    return (
      <View style={s.sqrtRow} testID="math-sqrt">
        {node.index ? (
          <View style={s.index}>
            <EditSlot
              text={input}
              group={node.index}
              caret={caret}
              before={before}
              after={after}
              testID="math-slot-nroot-index"
              onMoveCaret={onMoveCaret}
              fontSize={12}
              compact
            />
          </View>
        ) : null}
        <Text style={s.sqrtSign}>√</Text>
        <View style={s.sqrtBody} testID="math-sqrt-radicand">
          <EditSlot
            text={input}
            group={node.body}
            caret={caret}
            before={before}
            after={after}
            testID="math-slot-sqrt"
            onMoveCaret={onMoveCaret}
            compact
          />
        </View>
      </View>
    );
  }

  if (node.kind === "script") {
    const sub = node.mark === "_";
    return (
      <View style={s.inline} testID={sub ? "math-sub" : "math-sup"}>
        <View style={sub ? s.sub : s.sup}>
          <EditSlot
            text={input}
            group={node.body}
            caret={caret}
            before={before}
            after={after}
            testID={sub ? "math-slot-sub" : "math-slot-sup"}
            onMoveCaret={onMoveCaret}
          />
        </View>
      </View>
    );
  }

  if (node.kind === "brace") {
    return (
      <View style={s.inline} testID="math-brace">
        <EditSlot
          text={input}
          group={node.body}
          caret={caret}
          before={before}
          after={after}
          testID="math-slot-brace"
          onMoveCaret={onMoveCaret}
        />
      </View>
    );
  }

  if (node.kind === "abs") {
    return (
      <View style={s.inline} testID="math-abs">
        <Text style={s.prose}>|</Text>
        <EditSlot
          text={input}
          group={node.body}
          caret={caret}
          before={before}
          after={after}
          testID="math-slot-abs"
          onMoveCaret={onMoveCaret}
        />
        <Text style={s.prose}>|</Text>
      </View>
    );
  }

  if (node.kind === "binom") {
    return (
      <View style={s.inline} testID="math-binom">
        <Text style={s.prose}>C(</Text>
        <EditSlot
          text={input}
          group={node.n}
          caret={caret}
          before={before}
          after={after}
          testID="math-slot-binom-n"
          onMoveCaret={onMoveCaret}
        />
        <Text style={s.prose}>,</Text>
        <EditSlot
          text={input}
          group={node.k}
          caret={caret}
          before={before}
          after={after}
          testID="math-slot-binom-k"
          onMoveCaret={onMoveCaret}
        />
        <Text style={s.prose}>)</Text>
      </View>
    );
  }

  if (node.kind === "vec") {
    return (
      <View style={s.vec} testID="math-vec">
        <Text style={s.vecArrow}>→</Text>
        <EditSlot
          text={input}
          group={node.body}
          caret={caret}
          before={before}
          after={after}
          testID="math-slot-vec"
          onMoveCaret={onMoveCaret}
        />
      </View>
    );
  }

  const prefix = `${input.slice(node.start, node.body.open).replace(/\\/g, "")}${node.open}`;
  return (
    <View style={s.inline} testID="math-group">
      <Text style={s.prose}>{prefix}</Text>
      <EditSlot
        text={input}
        group={node.body}
        caret={caret}
        before={before}
        after={after}
        testID="math-slot-group"
        onMoveCaret={onMoveCaret}
      />
      <Text style={s.prose}>{node.close}</Text>
    </View>
  );
}

function EditSlot({
  text,
  group,
  caret,
  before,
  after,
  testID,
  onMoveCaret,
  compact = false,
  fontSize,
}: {
  text: string;
  group: LatexGroup;
  caret: number;
  before: number;
  after: number;
  testID: string;
  onMoveCaret?: (pos: number) => void;
  /** Radicand slot: the bar is this slot's top border, so the content needs a
   * tight line box or the digits hang well below it. */
  compact?: boolean;
  fontSize?: number;
}) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const widthRef = useRef(0);
  const inner = text.slice(group.open + 1, group.close);
  const empty = inner.length === 0;
  const nested = inner ? shiftDraftNodes(findDraftNodes(inner), group.open + 1) : [];
  const structured = nested.some((node) => node.kind !== "text");
  const focus = innermostSlot(text, caret);
  const active =
    focus != null && focus.open === group.open && focus.close === group.close;
  const atStart = active && caret === group.open + 1;
  const atEnd = active && caret === group.close;
  return (
    <Pressable
      testID={testID}
      onLayout={(e) => {
        widthRef.current = e.nativeEvent.layout.width;
      }}
      onPress={(e) => {
        if (!inner) {
          onMoveCaret?.(group.close);
          return;
        }
        const width = widthRef.current;
        const atFront = width > 0 && e.nativeEvent.locationX < width / 2;
        onMoveCaret?.(atFront ? group.open + 1 : group.close);
      }}
      style={[s.slot, empty && active && s.slotActive]}
      accessibilityRole="button"
    >
      <View style={s.slotRow}>
        {structured ? (
          nested.map((node, i) => (
            <DraftPiece
              key={`${node.kind}-${node.start}-${i}`}
              node={node}
              input={text}
              caret={caret}
              before={before}
              after={after}
              onMoveCaret={onMoveCaret}
            />
          ))
        ) : (
          <>
            {inner && atStart ? <MathComposerCaret testID={`${testID}-caret-start`} /> : null}
            {inner ? (
              <MathText latex={inner} textColor={theme.text} compact={compact} fontSize={fontSize} />
            ) : active ? (
              <View style={s.placeholderActive}>
                <MathComposerCaret testID={`${testID}-caret`} />
              </View>
            ) : (
              <View style={s.placeholder} testID={`${testID}-placeholder`} />
            )}
            {inner && atEnd ? <MathComposerCaret testID={`${testID}-caret-end`} /> : null}
          </>
        )}
      </View>
    </Pressable>
  );
}

const makeStyles = (theme: Theme) =>
  StyleSheet.create({
    wrap: {
      alignSelf: "flex-start",
      width: "100%",
      minHeight: MATH_DRAFT_PREVIEW_HEIGHT,
      justifyContent: "center",
      paddingHorizontal: 2,
      marginBottom: 2,
    },
    row: {
      flexDirection: "row",
      flexWrap: "wrap",
      alignItems: "center",
      justifyContent: "flex-start",
      gap: 1,
    },
    atom: {
      flexDirection: "row",
      alignItems: "center",
    },
    limitAtom: {
      alignItems: "center",
    },
    scriptStack: {
      marginLeft: 1,
      alignItems: "flex-start",
    },
    scriptOver: {
      alignItems: "center",
    },
    scriptLift: { marginBottom: 6 },
    scriptDrop: { marginTop: 6 },
    inline: {
      flexDirection: "row",
      alignItems: "center",
    },
    // Tops share an edge so the √ hook stays on the vinculum when the
    // radicand grows (MathText lineHeight 28). `center` dropped the glyph
    // and left a gap; `flex-end` would do the same once the slot is taller
    // than the sign.
    sqrtRow: {
      flexDirection: "row",
      alignItems: "flex-start",
    },
    prose: {
      fontSize: 16,
      color: theme.text,
    },
    sqrtSign: {
      fontSize: 16,
      lineHeight: 20,
      color: theme.text,
    },
    frac: {
      alignItems: "center",
      minWidth: 28,
    },
    vinculum: {
      alignSelf: "stretch",
      height: StyleSheet.hairlineWidth,
      backgroundColor: theme.text,
      marginVertical: 2,
    },
    sqrtBody: {
      borderTopWidth: StyleSheet.hairlineWidth * 2,
      borderTopColor: theme.text,
      paddingTop: 1,
      marginLeft: 1,
    },
    // Place the degree above the root hook. Scaling a full-height edit slot
    // around its centre left the old degree looking like a coefficient.
    index: { marginRight: -4, marginTop: -6 },
    vec: {
      alignItems: "center",
    },
    vecArrow: {
      fontSize: 12,
      lineHeight: 12,
      color: theme.text,
      marginBottom: -2,
    },
    sup: { marginBottom: 2 },
    sub: { marginTop: 2 },
    slot: {
      minWidth: 12,
      minHeight: 16,
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: 1,
    },
    slotActive: {
      backgroundColor: theme.primaryLight,
      borderRadius: 4,
    },
    slotRow: {
      flexDirection: "row",
      alignItems: "center",
    },
    textHit: {
      paddingHorizontal: 2,
      minHeight: 22,
      justifyContent: "center",
    },
    placeholder: {
      width: 10,
      height: 14,
      borderRadius: 2,
      backgroundColor: "transparent",
      borderBottomWidth: 1,
      borderBottomColor: theme.textTertiary,
    },
    placeholderActive: {
      width: 10,
      height: 14,
      borderRadius: 2,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: theme.primaryLight,
      borderBottomWidth: 1,
      borderBottomColor: theme.primary,
    },
    edge: {
      minWidth: 6,
      minHeight: 22,
      alignItems: "center",
      justifyContent: "center",
    },
  });
