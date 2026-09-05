import { useEffect, useMemo, useRef } from "react";
import { StyleSheet, View } from "react-native";
import Animated, {
  cancelAnimation,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSpring,
  withTiming,
} from "react-native-reanimated";

import { Icon } from "@/components/Icon";
import type { ChapterAccess } from "@/lib/projects/chapterAccess";
import { domainIcon } from "@/lib/projects/domainIcons";
import { Motion, useReduceMotion } from "@/lib/motion";
import { shadowGlow } from "@/lib/shadow";
import { Theme, useTheme } from "@/lib/theme";

const NODE = 52;
const PULSE_SCALE = 1.08;

type Props = {
  access: ChapterAccess;
  domainTitle: string;
  justCompleted: boolean;
};

export function LearningPathNode({ access, domainTitle, justCompleted }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const reduceMotion = useReduceMotion();
  const scale = useSharedValue(1);
  const unlockPlayed = useRef(false);
  const current = access === "current";
  const done = access === "done";
  const locked = access === "locked";
  const animate = !reduceMotion && (current || justCompleted);

  useEffect(() => {
    cancelAnimation(scale);
    if (reduceMotion) {
      scale.value = 1;
      return () => cancelAnimation(scale);
    }
    if (justCompleted) {
      if (!unlockPlayed.current) {
        unlockPlayed.current = true;
        scale.value = 0.72;
        scale.value = withSpring(1, { damping: 18, stiffness: 160 });
      }
      return () => cancelAnimation(scale);
    }
    if (!current) {
      scale.value = 1;
      return () => cancelAnimation(scale);
    }
    scale.value = 1;
    scale.value = withRepeat(
      withTiming(PULSE_SCALE, { duration: Motion.duration.soft, easing: Motion.easing.inOut }),
      -1,
      true,
    );
    return () => {
      cancelAnimation(scale);
      scale.value = 1;
    };
  }, [current, justCompleted, reduceMotion, scale]);

  const pulse = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
  }));

  return (
    <Animated.View
      testID={justCompleted ? "path-node-unlock" : current ? "path-node-current" : undefined}
      style={[
        s.node,
        done ? s.nodeDone : null,
        current ? s.nodeCurrent : null,
        locked ? s.nodeLocked : null,
        current ? shadowGlow(theme, theme.primary) : null,
        animate ? pulse : null,
      ]}
    >
      <Icon
        name={done ? "checkmark" : domainIcon(domainTitle)}
        size={done ? 22 : 24}
        color={locked ? theme.textTertiary : theme.onPrimary}
      />
      {locked ? (
        <View style={s.lockBadge}>
          <Icon name="lock-closed-outline" size={11} color={theme.textTertiary} />
        </View>
      ) : null}
    </Animated.View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    node: {
      width: NODE,
      height: NODE,
      borderRadius: NODE / 2,
      alignItems: "center",
      justifyContent: "center",
    },
    nodeCurrent: { backgroundColor: theme.primary },
    nodeDone: { backgroundColor: theme.success },
    nodeLocked: {
      backgroundColor: theme.surfaceAlt,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    lockBadge: {
      position: "absolute",
      bottom: -3,
      right: -3,
      width: 20,
      height: 20,
      borderRadius: 10,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: theme.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
  });
}
