import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import Svg, { Line, Polyline } from "react-native-svg";

import { AccessibleElementChildren } from "@/components/rich/accessibleElement";
import { RichMathBody, richTextLabel } from "@/components/rich/RichMathBody";
import { PARAGRAPH_GAP } from "@/components/markdown/markdownContentStyles";
import i18n from "@/lib/i18n";
import { Radius } from "@/lib/radius";
import { stepParts } from "@/lib/richBlocks";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { DYNAMIC_TYPE_MAX, Type, Weight } from "@/lib/type";

type Props = { steps: string[] };

// A title bold as a whole: the box sets every title bold, and its `code` inside the marks
// would show its backticks ("**Read `2` at index `0`**").
const WHOLLY_BOLD = /^\*\*(?!.*\*\*.*\*\*)(.+)\*\*$/;

// The arrow between two boxes: a short shaft and an open head, drawn in its own box.
const ARROW_WIDTH = 16;
const ARROW_HEIGHT = 20;

/**
 * A ```steps card drawn as a flow: each step a box, its number and bold title, then its
 * lines, joined to the next by an arrow. "If I ask how to do something, I need to see a
 * flow with arrows" (the owner, 2026-11-14). A step's `$…$` is drawn as maths.
 */
export function StepFlow({ steps }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <View style={s.wrap} testID="step-flow">
      {steps.map((step, index) => {
        const { title, body } = stepParts(step);
        const label = `${i18n.t("rich.step_flow_a11y", { n: index + 1, total: steps.length })}: ${richTextLabel(step.replace(/\n/g, ". "))}`;
        return (
          <View key={`step-${index}`}>
            {index > 0 ? <FlowArrow color={theme.textTertiary} /> : null}
            <View
              style={s.box}
              testID="step-flow-box"
              accessible
              accessibilityRole="text"
              accessibilityLabel={label}
            >
              <AccessibleElementChildren>
                <View style={s.head}>
                  <View style={s.badge}>
                    <Text style={s.badgeText} maxFontSizeMultiplier={DYNAMIC_TYPE_MAX}>
                      {index + 1}
                    </Text>
                  </View>
                  <RichMathBody content={title.replace(WHOLLY_BOLD, "$1")} style={s.title} />
                </View>
                {body ? <RichMathBody content={body} style={s.body} /> : null}
              </AccessibleElementChildren>
            </View>
          </View>
        );
      })}
    </View>
  );
}

/** Decorative: the boxes' labels already say which step comes when. */
function FlowArrow({ color }: { color: string }) {
  const mid = ARROW_WIDTH / 2;
  return (
    <View
      style={styles.arrow}
      testID="step-flow-arrow"
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      <Svg width={ARROW_WIDTH} height={ARROW_HEIGHT}>
        <Line x1={mid} y1={1} x2={mid} y2={ARROW_HEIGHT - 2} stroke={color} strokeWidth={1.5} strokeLinecap="round" />
        <Polyline
          points={`${mid - 5},${ARROW_HEIGHT - 7} ${mid},${ARROW_HEIGHT - 2} ${mid + 5},${ARROW_HEIGHT - 7}`}
          fill="none"
          stroke={color}
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </Svg>
    </View>
  );
}

const styles = StyleSheet.create({
  arrow: { alignItems: "center", paddingVertical: Space.xxs },
});

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: { marginTop: 0, marginBottom: PARAGRAPH_GAP },
    box: {
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      gap: Space.xs,
      borderRadius: Radius.md,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      backgroundColor: t.surface,
    },
    head: { flexDirection: "row", gap: Space.sm, alignItems: "flex-start" },
    // Grows into a pill when large text makes the number wider than 24pt.
    badge: {
      minWidth: 24,
      minHeight: 24,
      paddingHorizontal: Space.xxs,
      borderRadius: Radius.full,
      backgroundColor: t.primaryLight,
      alignItems: "center",
      justifyContent: "center",
      flexShrink: 0,
    },
    badgeText: { ...Type.compact, ...Weight.bold, color: t.primary },
    title: { flex: 1, ...Type.body, ...Weight.semibold, color: t.text, marginTop: 1 },
    body: { ...Type.body, color: t.textSecondary },
  });
}
