import { memo, useMemo } from "react";
import { StyleSheet, View } from "react-native";
import { useTranslation } from "react-i18next";

import { AccessibleElementChildren } from "@/components/rich/accessibleElement";
import { MathText } from "@/components/rich/MathText";
import { liveAnswer } from "@/lib/math/live/answer";
import { MATH_TALL_LINE_HEIGHT } from "@/lib/math/text";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

/**
 * The answer line's height. The line keeps it while the math keyboard is open, answer or
 * not, so the composer does not jump between keys (`3+1×` has none, `3+1×2` has one); it is
 * tall enough for a stacked fraction.
 */
export const MATH_LIVE_ANSWER_HEIGHT = MATH_TALL_LINE_HEIGHT;
/** Larger than the draft's 16, as a calculator's result is. */
const ANSWER_SIZE = 20;

/**
 * Under the draft while the math keyboard is open: its value as each key lands (`= 5` for
 * `3+1×2`), worked on the phone (`lib/math/live/answer.ts`). Send still asks the server.
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
          <MathText latex={answer.latex} textColor={theme.textSecondary} fontSize={ANSWER_SIZE} />
        </AccessibleElementChildren>
      ) : null}
    </View>
  );
});

const styles = StyleSheet.create({
  line: {
    height: MATH_LIVE_ANSWER_HEIGHT,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "flex-end",
    paddingHorizontal: Space.sm,
    overflow: "hidden",
  },
});
