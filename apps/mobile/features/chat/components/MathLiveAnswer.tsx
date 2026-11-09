import { memo, useMemo } from "react";
import { StyleSheet, View } from "react-native";
import { useTranslation } from "react-i18next";

import { AccessibleElementChildren } from "@/components/rich/accessibleElement";
import { MathText } from "@/components/rich/MathText";
import { MATH_DRAFT_PREVIEW_HEIGHT } from "@/features/chat/components/MathDraftPreview";
import { ACCENTS } from "@/lib/accent";
import { liveAnswer } from "@/lib/math/live/answer";
import { MATH_TALL_LINE_HEIGHT } from "@/lib/math/text";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

/**
 * The answer's height, which the row of buttons under the draft takes while the math keyboard
 * is open, answer or not, so the composer does not jump between keys (`3+1×` has none,
 * `3+1×2` has one); it is tall enough for a stacked fraction.
 */
export const MATH_LIVE_ANSWER_HEIGHT = MATH_TALL_LINE_HEIGHT;
/** Larger than the draft's 16, as a calculator's result is. */
const ANSWER_SIZE = 20;

/**
 * While the math keyboard is open the composer opens full height, as its expand control
 * would: the draft at the top, its answer at the bottom. Its empty caret and placeholder sit
 * on the draft's first line, not on the field's midline or its last.
 */
export const mathCardStyles = StyleSheet.create({
  // The field fills the card's height, so the draft starts at its top, not by the buttons.
  field: { alignSelf: "stretch", justifyContent: "flex-start" },
  emptyCaret: { bottom: undefined, height: MATH_DRAFT_PREVIEW_HEIGHT },
});

/**
 * At the bottom of the composer while the math keyboard is open, between + and Send: the
 * draft's value as each key lands (`= 5` for `3+1×2`), worked on the phone
 * (`lib/math/live/answer.ts`), in the green accent whatever accent the app wears. Send still
 * asks the server.
 */
export const MathLiveAnswer = memo(function MathLiveAnswer({ input }: { input: string }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const answer = useMemo(() => liveAnswer(input), [input]);
  return (
    <View
      style={styles.line}
      testID="math-live-answer"
      accessible={answer != null}
      accessibilityLabel={answer ? t("chat.math_live_answer_a11y", { value: answer.spoken }) : undefined}
    >
      {answer ? (
        <AccessibleElementChildren>
          <MathText latex={answer.latex} textColor={ACCENTS.green[theme.scheme].primary} fontSize={ANSWER_SIZE} />
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
    justifyContent: "flex-end",
    paddingHorizontal: Space.sm,
    overflow: "hidden",
  },
});
