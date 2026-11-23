import { memo, useMemo } from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { useTranslation } from "react-i18next";

import { AccessibleElementChildren } from "@/components/rich/accessibleElement";
import { useFlashWhenClipped } from "@/components/rich/clippedScroll";
import { MathText } from "@/components/rich/MathText";
import { MATH_DRAFT_PREVIEW_HEIGHT } from "@/features/chat/components/MathDraftPreview";
import { COMPOSER_CONTROL_SIZE } from "@/features/chat/model/composerLogic";
import { ACCENTS } from "@/lib/accent";
import { layoutMath } from "@/lib/math/layout";
import { liveAnswer } from "@/lib/math/live/answer";
import { fixImplicitExponents } from "@/lib/math/normalizeImplicit";
import { MATH_TALL_LINE_HEIGHT, parseSimpleLatex } from "@/lib/math/text";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

/**
 * The answer's height, which the row of buttons under the draft takes while the math keyboard
 * is open. Once the draft has a key in it the row keeps it, answer or not, so the composer
 * does not jump between keys (`3+1×` has none, `3+1×2` has one); it is tall enough for a
 * stacked fraction.
 */
export const MATH_LIVE_ANSWER_HEIGHT = MATH_TALL_LINE_HEIGHT;
/** The answer's row waits for the draft's first key: an empty draft is one line, not three. */
export function liveAnswerShows(input: string): boolean {
  return input.trim().length > 0;
}

/** Larger than the draft's 16, as a calculator's result is. */
const ANSWER_SIZE = 20;
/** A ± draft's branches echo the draft, so they take its size: a stacked one still fits the row. */
const BRANCH_SIZE = 16;

const heightOf = (latex: string, size: number): number =>
  layoutMath(parseSimpleLatex(fixImplicitExponents(latex.trim())), size).height;

/**
 * The tallest the row holds: a fraction answer (`= \frac{5}{6}`) at the answer's size, as
 * `MathText` lays it out. Text size scales both alike, so the comparison leaves it out.
 */
const ROW_LIMIT = heightOf("= \\frac{5}{6}", ANSWER_SIZE);
const fitsRow = (latex: string, size: number): boolean => heightOf(latex, size) <= ROW_LIMIT;

/**
 * While the math keyboard is open the composer opens full height, as its expand control
 * would: the draft at the top, its answer at the bottom. Expanded, its empty caret and
 * placeholder sit on the draft's first line, not on the field's midline or its last.
 */
export const mathCardStyles = StyleSheet.create({
  // The field fills the card's height, so the draft starts at its top, not by the buttons.
  field: { alignSelf: "stretch", justifyContent: "flex-start" },
  emptyCaret: { bottom: undefined, height: MATH_DRAFT_PREVIEW_HEIGHT },
  // Where + stood beside the answer, so the answer sits in the row's middle.
  answerBalance: { width: COMPOSER_CONTROL_SIZE },
});

/**
 * At the bottom of the composer while the math keyboard is open, in the row's middle: the
 * draft's value as each key lands (`= 5` for `3+1×2`, `= undefined` for `1÷0`, both branches
 * of `2±1`), worked on the phone (`lib/math/live/answer.ts`), in the green accent whatever
 * accent the app wears. An answer wider than the row scrolls sideways. Send still asks the
 * server.
 */
export const MathLiveAnswer = memo(function MathLiveAnswer({ input }: { input: string }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const undefinedWord = t("chat.math_live_undefined");
  const answer = useMemo(() => liveAnswer(input, undefinedWord), [input, undefinedWord]);
  const color = ACCENTS.green[theme.scheme].primary;
  const size = answer?.signed ? BRANCH_SIZE : ANSWER_SIZE;
  // Branches that echo a tall draft (a fraction in a fraction) show their values alone.
  const latex = useMemo(
    () => (answer?.short && !fitsRow(answer.latex, size) ? answer.short : answer?.latex),
    [answer, size],
  );
  // Wider than the row, its scroll bar shows once, so a cut edge reads as more to see.
  const flash = useFlashWhenClipped();
  return (
    <View
      style={styles.line}
      testID="math-live-answer"
      accessible={answer != null}
      accessibilityLabel={answer ? t("chat.math_live_answer_a11y", { value: answer.spoken }) : undefined}
    >
      {answer ? (
        <AccessibleElementChildren>
          <ScrollView
            {...flash}
            horizontal
            showsHorizontalScrollIndicator
            bounces={false}
            keyboardShouldPersistTaps="handled"
            contentContainerStyle={styles.content}
          >
            <MathText latex={latex ?? answer.latex} textColor={color} fontSize={size} />
          </ScrollView>
        </AccessibleElementChildren>
      ) : null}
    </View>
  );
});

const styles = StyleSheet.create({
  line: {
    flex: 1,
    height: MATH_LIVE_ANSWER_HEIGHT,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: Space.sm,
    overflow: "hidden",
  },
  // Centred while the answer fits the row; wider, it scrolls from its start.
  content: { flexGrow: 1, alignItems: "center", justifyContent: "center" },
});
