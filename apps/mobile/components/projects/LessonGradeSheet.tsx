import { useEffect } from "react";
import { StyleSheet, Text, View } from "react-native";
import Animated, {
  SlideOutDown,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  withTiming,
} from "react-native-reanimated";
import { useTranslation } from "react-i18next";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";
import { Motion, useReduceMotion } from "@/lib/motion";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

const SLIDE = 64;

type Props = {
  correct: boolean;
  explanation: string;
  error?: string | null;
  showContinue?: boolean;
  textScale?: number;
  onContinue?: () => void;
  onRetry?: () => void;
};

export function LessonGradeSheet({
  correct,
  explanation,
  error,
  showContinue = false,
  textScale = 1,
  onContinue,
  onRetry,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const s = makeStyles(theme, textScale);
  const reduceMotion = useReduceMotion();
  const offset = useSharedValue(reduceMotion ? 0 : SLIDE);
  const opacity = useSharedValue(reduceMotion ? 1 : 0);

  useEffect(() => {
    if (reduceMotion) {
      offset.value = 0;
      opacity.value = 1;
      return;
    }
    offset.value = SLIDE;
    opacity.value = 0;
    offset.value = withSpring(0, { damping: 18, stiffness: 220 });
    opacity.value = withTiming(1, {
      duration: Motion.duration.snappy,
      easing: Motion.easing.out,
    });
  }, [correct, explanation, offset, opacity, reduceMotion]);

  const slide = useAnimatedStyle(() => ({
    transform: [{ translateY: offset.value }],
    opacity: opacity.value,
  }));

  return (
    <Animated.View
      exiting={
        reduceMotion
          ? undefined
          : SlideOutDown.duration(Motion.duration.standard).easing(Motion.easing.in)
      }
      style={[
        s.sheet,
        {
          backgroundColor: correct ? theme.successLight : theme.dangerLight,
          paddingBottom: Space.lg + insets.bottom,
        },
        slide,
      ]}
      accessibilityLiveRegion="polite"
      accessibilityRole="summary"
    >
      <View style={s.copyRow}>
        <Icon
          name={correct ? "checkmark-circle" : "close-circle"}
          size={24}
          color={correct ? theme.success : theme.danger}
        />
        <View style={s.copy}>
          {correct ? (
            <Text style={[s.heading, { color: theme.success }]}>{t("lesson.correct")}</Text>
          ) : null}
          <Text style={s.body}>{explanation}</Text>
        </View>
      </View>
      {error ? (
        <>
          <Text style={s.error}>{error}</Text>
          {onRetry ? <Button title={t("common.retry")} onPress={onRetry} /> : null}
        </>
      ) : showContinue && onContinue ? (
        <Button title={t("lesson.continue")} onPress={onContinue} style={s.nextBtn} />
      ) : null}
    </Animated.View>
  );
}

function makeStyles(theme: Theme, scale: number) {
  const n = (size: number) => Math.round(size * scale);
  return StyleSheet.create({
    sheet: {
      paddingHorizontal: Space.lg,
      paddingTop: Space.lg,
      borderTopLeftRadius: Radius.sheet,
      borderTopRightRadius: Radius.sheet,
      gap: Space.md,
    },
    copyRow: {
      flexDirection: "row",
      alignItems: "flex-start",
      gap: Space.sm,
    },
    copy: { flex: 1, gap: Space.xxs },
    heading: { ...Type.body, fontWeight: "700", fontSize: n(16) },
    body: { ...Type.body, color: theme.text, fontSize: n(16), lineHeight: n(26) },
    error: {
      ...Type.secondary,
      color: theme.danger,
      textAlign: "center",
    },
    nextBtn: {
      minHeight: 52,
      borderRadius: 18,
    },
  });
}
