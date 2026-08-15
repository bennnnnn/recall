import { memo, useMemo, useRef } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { MathText } from "@/components/rich/MathText";
import { splitInlineMath } from "@/lib/markdownPreprocess";
import {
  caretAfterExpression,
  caretBeforeExpression,
  findDraftNodes,
  type DraftNode,
} from "@/lib/mathDraftSlots";
import { caretInGroup, type LatexGroup } from "@/lib/mathKeyboardSymbols";
import { latexNeedsTallLine, MATH_TALL_LINE_HEIGHT } from "@/lib/mathText";
import { Theme, useTheme } from "@/lib/theme";

export const MATH_DRAFT_PREVIEW_HEIGHT = 48;

export function draftShowsMathPreview(input: string): boolean {
  return input.includes("$") && input.trim().length > 0;
}

type Props = {
  input: string;
  caret?: number;
  onMoveCaret?: (pos: number) => void;
};

export const MathDraftPreview = memo(function MathDraftPreview({
  input,
  caret = 0,
  onMoveCaret,
}: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const nodes = useMemo(() => findDraftNodes(input), [input]);
  const parts = useMemo(() => splitInlineMath(input), [input]);
  const before = caretBeforeExpression(input);
  const after = caretAfterExpression(input);
  const tall = parts.some((p) => p.type === "math" && latexNeedsTallLine(p.value));
  if (!draftShowsMathPreview(input)) return null;

  return (
    <View style={[s.wrap, s.row, tall && { minHeight: MATH_TALL_LINE_HEIGHT }]} testID="math-draft-preview">
      <Pressable
        testID="math-slot-before"
        onPress={() => onMoveCaret?.(before)}
        style={[s.edge, caret <= before && s.slotActive]}
        accessibilityRole="button"
      >
        {caret <= before ? <View style={s.caret} testID="math-slot-before-caret" /> : null}
      </Pressable>
      {nodes.map((node, i) => (
        <DraftPiece
          key={`${node.kind}-${node.start}-${i}`}
          node={node}
          input={input}
          caret={caret}
          onMoveCaret={onMoveCaret}
        />
      ))}
      <Pressable
        testID="math-slot-after"
        onPress={() => onMoveCaret?.(after)}
        style={[s.edge, caret >= after && s.slotActive]}
        accessibilityRole="button"
      >
        {caret >= after ? <View style={s.caret} testID="math-slot-after-caret" /> : null}
      </Pressable>
    </View>
  );
});

function DraftPiece({
  node,
  input,
  caret,
  onMoveCaret,
}: {
  node: DraftNode;
  input: string;
  caret: number;
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
        {/\\/.test(display) ? (
          <MathText latex={display} textColor={theme.text} />
        ) : (
          <Text style={s.prose}>{display}</Text>
        )}
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
      <View style={s.inline} testID="math-sqrt">
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
        <Text style={s.prose}>√</Text>
        <View style={s.sqrtBody}>
          <EditSlot
            text={input}
            group={node.body}
            caret={caret}
            testID="math-slot-sqrt"
            onMoveCaret={onMoveCaret}
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
}: {
  text: string;
  group: LatexGroup;
  caret: number;
  testID: string;
  onMoveCaret?: (pos: number) => void;
}) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const widthRef = useRef(0);
  const inner = text.slice(group.open + 1, group.close);
  const atStart = caret === group.open + 1;
  const atEnd = caret === group.close;
  const active = caretInGroup(caret, group);
  return (
    <Pressable
      testID={testID}
      onLayout={(e) => {
        widthRef.current = e.nativeEvent.layout.width;
      }}
      onPress={(e) => {
        const width = widthRef.current;
        const atFront = width > 0 && e.nativeEvent.locationX < width / 2;
        onMoveCaret?.(atFront ? group.open + 1 : group.close);
      }}
      style={[s.slot, active && s.slotActive]}
      accessibilityRole="button"
    >
      <View style={s.slotRow}>
        {inner && atStart ? <View style={s.caret} testID={`${testID}-caret-start`} /> : null}
        {inner ? (
          <MathText latex={inner} textColor={theme.text} />
        ) : active ? (
          <View style={s.caret} testID={`${testID}-caret`} />
        ) : (
          <View style={s.empty} />
        )}
        {inner && atEnd ? <View style={s.caret} testID={`${testID}-caret-end`} /> : null}
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
    prose: {
      fontSize: 16,
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
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: theme.text,
      marginLeft: 1,
    },
    index: { marginRight: -2, marginBottom: 10 },
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
    empty: {
      width: 12,
      height: 14,
    },
    caret: {
      width: 2,
      height: 16,
      backgroundColor: theme.primary,
      borderRadius: 1,
    },
    edge: {
      minWidth: 18,
      minHeight: 28,
      alignItems: "center",
      justifyContent: "center",
    },
  });
