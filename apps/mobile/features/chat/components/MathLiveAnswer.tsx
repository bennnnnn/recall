import { memo, useMemo, type ReactNode } from "react";
import { ScrollView, StyleSheet, useWindowDimensions, View } from "react-native";
import { useTranslation } from "react-i18next";

import { AccessibleElementChildren } from "@/components/rich/accessibleElement";
import { useFlashWhenClipped } from "@/components/rich/clippedScroll";
import { MathText, mathHeight } from "@/components/rich/MathText";
import { MATH_DRAFT_PREVIEW_HEIGHT } from "@/features/chat/components/MathDraftPreview";
import { COMPOSER_CONTROL_SIZE } from "@/features/chat/model/composerLogic";
import { ACCENTS } from "@/lib/accent";
import { DRAFT_TEXT_SIZE } from "@/lib/math/draftText";
import { liveAnswer } from "@/lib/math/live/answer";
import { MATH_TALL_LINE_HEIGHT } from "@/lib/math/text";
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
const BRANCH_SIZE = DRAFT_TEXT_SIZE;

/**
 * Whether `latex` at `size`, as `MathText` lays it out and the system text size scales it, is no
 * taller than the row that clips it.
 */
const fitsRow = (latex: string, size: number, fontScale: number): boolean =>
  mathHeight(latex, size) * fontScale <= MATH_LIVE_ANSWER_HEIGHT;

/** A value at the answer's size that the system text size grows past the row it fits at 1×. */
function grownPastRow(latex: string, fontScale: number): boolean {
  const height = mathHeight(latex, ANSWER_SIZE);
  return height * fontScale > Math.max(MATH_LIVE_ANSWER_HEIGHT, height);
}

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
 * The answer's sideways scroll, one per answer shown (its caller keys it): wider than the row,
 * its bar shows once, so a cut edge reads as more to see, again for each new wide answer.
 */
function AnswerScroll({ children }: { children: ReactNode }) {
  const flash = useFlashWhenClipped();
  return (
    <ScrollView
      {...flash}
      // The row's View is the one screen-reader stop; on Android a scroll view would be another.
      accessible={false}
      importantForAccessibility="no"
      horizontal
      showsHorizontalScrollIndicator
      bounces={false}
      keyboardShouldPersistTaps="handled"
      style={styles.scroll}
      contentContainerStyle={styles.content}
    >
      {children}
    </ScrollView>
  );
}

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
  const { fontScale } = useWindowDimensions();
  // A value a larger system text size makes too tall for the row (`\frac{1}{3}` at 1.3) takes the
  // draft's size, as ± branches always do; at the standard size the row is drawn for it.
  const size = answer?.signed || (answer && grownPastRow(answer.latex, fontScale)) ? BRANCH_SIZE : ANSWER_SIZE;
  // Branches that echo a tall draft (a fraction in a fraction) show their values alone, when
  // those are lower: at a large text size even a fraction's values may not fit.
  const latex = useMemo((): string | null => {
    if (!answer) return null;
    if (!answer.short || fitsRow(answer.latex, size, fontScale)) return answer.latex;
    return mathHeight(answer.short, size) < mathHeight(answer.latex, size) ? answer.short : answer.latex;
  }, [answer, size, fontScale]);
  return (
    <View
      style={styles.line}
      testID="math-live-answer"
      accessible={answer != null}
      accessibilityLabel={answer ? t("chat.math_live_answer_a11y", { value: answer.spoken }) : undefined}
    >
      {latex ? (
        <AccessibleElementChildren>
          <AnswerScroll key={latex}>
            <MathText latex={latex} textColor={color} fontSize={size} />
          </AnswerScroll>
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
  // The row's full height, so a tall answer is centred in it and the flashed bar stays in view.
  scroll: { alignSelf: "stretch" },
});
