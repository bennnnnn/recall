import type { ReactNode } from "react";
import { StyleSheet } from "react-native";
import Animated, { SlideInRight, SlideOutLeft } from "react-native-reanimated";

import { Motion, useReduceMotion } from "@/lib/motion";

type Props = {
  stepKey: string;
  fill?: boolean;
  children: ReactNode;
};

export function LessonStepTransition({ stepKey, fill = false, children }: Props) {
  const reduceMotion = useReduceMotion();
  const entering = reduceMotion
    ? undefined
    : SlideInRight.duration(Motion.duration.standard).easing(Motion.easing.out);
  const exiting = reduceMotion
    ? undefined
    : SlideOutLeft.duration(Motion.duration.standard).easing(Motion.easing.in);
  return (
    <Animated.View
      key={stepKey}
      testID="lesson-pane"
      entering={entering}
      exiting={exiting}
      style={fill ? styles.fill : undefined}
    >
      {children}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  fill: { flexGrow: 1 },
});
