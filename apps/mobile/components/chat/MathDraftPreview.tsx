import { memo, useMemo, useRef } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { MathComposerCaret } from "@/components/chat/MathComposerCaret";
import { MathText } from "@/components/rich/MathText";
import { splitInlineMath } from "@/lib/markdownPreprocess";
import { textLooksLikeMath } from "@/lib/mathComposerIntent";
import {
  caretAfterExpression,
  caretBeforeExpression,
  findDraftNodes,
  type DraftNode,
} from "@/lib/mathDraftSlots";
import { innermostSlot, type LatexGroup } from "@/lib/mathKeyboardSymbols";
import { latexNeedsTallLine, MATH_TALL_LINE_HEIGHT } from "@/lib/mathText";
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
  if (input.includes("$")) return true;
  return textLooksLikeMath(input);
}

/**
 * True when a *sent* user message should render via `MathDraftPreview`.
 * Unlike the composer, sent messages only use the preview when the user
 * explicitly wrapped math in `$...$` — bare equations in sent messages
 * render through the normal markdown path (which handles implicit math).
 */
export function sentMessageShowsMathPreview(input: string): boolean {
  return input.includes("$") && input.trim().length > 0;
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
  const mathInput = useMemo(
    () => (input.includes("$") ? input : `$${input}$`),
    [input],
  );
  const nodes = useMemo(() => findDraftNodes(mathInput), [mathInput]);
  const parts = useMemo(() => splitInlineMath(mathInput), [mathInput]);
  const before = caretBeforeExpression(mathInput);
  const after = caretAfterExpression(mathInput);
  const tall = parts.some((p) => p.type === "math" && latexNeedsTallLine(p.value));
  if (!draftShowsMathPreview(input)) return null;
  const liveCaret = showCaret && caret >= 0;
  const showBeforeCaret = liveCaret && caret <= before && caret < after;
  const showAfterCaret = liveCaret && caret >= after;

  return (
    <View style={[s.wrap, s.row, tall && { minHeight: MATH_TALL_LINE_HEIGHT }]} testID="math-draft-preview">
      <Pressable
        testID="math-slot-before"
        onPress={() => onMoveCaret?.(before)}
        style={[s.edge, showBeforeCaret && s.slotActive]}
        accessibilityRole="button"
      >
        {showBeforeCaret ? <MathComposerCaret testID="math-slot-before-caret" /> : null}
      </Pressable>
      {nodes.map((node, i) => (
        <DraftPiece
          key={`${node.kind}-${node.start}-${i}`}
          node={node}
          input={mathInput}
          caret={liveCaret ? caret : -1}
          before={before}
          after={after}
          onMoveCaret={onMoveCaret}
        />
      ))}
      <Pressable
        testID="math-slot-after"
        onPress={() => onMoveCaret?.(after)}
        style={[s.edge, showAfterCaret && s.slotActive]}
        accessibilityRole="button"
      >
        {showAfterCaret ? <MathComposerCaret testID="math-slot-after-caret" /> : null}
      </Pressable>
    </View>
  );
});

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
    const display = input.slice(node.start, node.end).replace(/\$/g, "");
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
        style={[s.textHit, caret >= start && caret <= end && s.slotActive]}
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
          testID="math-slot-num"
          onMoveCaret={onMoveCaret}
        />
        <View style={s.vinculum} testID="math-vinculum" />
        <EditSlot
          text={input}
          group={node.den}
          caret={caret}
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
              testID="math-slot-nroot-index"
              onMoveCaret={onMoveCaret}
            />
          </View>
        ) : null}
        <Text style={s.sqrtSign}>√</Text>
        <View style={s.sqrtBody} testID="math-sqrt-radicand">
          <EditSlot
            text={input}
            group={node.body}
            caret={caret}
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
            testID={sub ? "math-slot-sub" : "math-slot-sup"}
            onMoveCaret={onMoveCaret}
          />
        </View>
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
          testID="math-slot-abs"
          onMoveCaret={onMoveCaret}
        />
        <Text style={s.prose}>|</Text>
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
  testID,
  onMoveCaret,
  compact = false,
}: {
  text: string;
  group: LatexGroup;
  caret: number;
  testID: string;
  onMoveCaret?: (pos: number) => void;
  /** Radicand slot: the bar is this slot's top border, so the content needs a
   * tight line box or the digits hang well below it. */
  compact?: boolean;
}) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const widthRef = useRef(0);
  const inner = text.slice(group.open + 1, group.close);
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
      style={[s.slot, active && s.slotActive]}
      accessibilityRole="button"
    >
      <View style={s.slotRow}>
        {inner && atStart ? <MathComposerCaret testID={`${testID}-caret-start`} /> : null}
        {inner ? (
          <MathText latex={inner} textColor={theme.text} compact={compact} />
        ) : active ? (
          <View style={s.placeholderActive}>
            <MathComposerCaret testID={`${testID}-caret`} />
          </View>
        ) : (
          <View style={s.placeholder} testID={`${testID}-placeholder`} />
        )}
        {inner && atEnd ? <MathComposerCaret testID={`${testID}-caret-end`} /> : null}
      </View>
    </Pressable>
  );
}

const makeStyles = (theme: Theme) =>
  StyleSheet.create({
    wrap: {
      minHeight: MATH_DRAFT_PREVIEW_HEIGHT,
      justifyContent: "center",
      paddingHorizontal: 2,
      marginBottom: 2,
    },
    row: {
      flexDirection: "row",
      flexWrap: "wrap",
      alignItems: "center",
      gap: 4,
    },
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
    index: { marginRight: 0, marginTop: -2, transform: [{ scale: 0.72 }] },
    sup: { marginBottom: 10 },
    sub: { marginTop: 10 },
    slot: {
      minWidth: 22,
      minHeight: 18,
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: 4,
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
      width: 16,
      height: 18,
      borderRadius: 4,
      backgroundColor: theme.surfaceAlt,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.textTertiary,
    },
    placeholderActive: {
      width: 16,
      height: 18,
      borderRadius: 4,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: theme.primaryLight,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.primary,
    },
    edge: {
      minWidth: 18,
      minHeight: 28,
      alignItems: "center",
      justifyContent: "center",
    },
  });
