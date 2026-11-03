import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { Pressable } from "react-native-gesture-handler";
import Animated, { type SharedValue } from "react-native-reanimated";
import { useTranslation } from "react-i18next";

import {
  pauseReadAloud,
  readAloudElapsedMs,
  readAloudSession,
  resumeReadAloud,
  stopReadAloud,
  type ReadAloud,
} from "@/features/speech/model/readAloudSession";
import { tap } from "@/lib/haptics";
import { Layer } from "@/lib/layer";
import { Radius } from "@/lib/radius";
import { shadowElevated } from "@/lib/shadow";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";
import { useBottomLiftStyle } from "@/ui/hooks/useBottomLiftStyle";

/** The player's height, so what floats over the composer (the scroll button) sits above it. */
export const READ_ALOUD_PLAYER_HEIGHT = 48;

/** A reply is being read aloud: the player shows over the composer. */
export function useReadAloudShowing(): boolean {
  return useSyncExternalStore(readAloudSession.subscribe, () => readAloudSession.get() !== null);
}

type Props = {
  visible: boolean;
  bottomOffset: number;
  /** Rides the keyboard with the composer, frame by frame. */
  lift?: SharedValue<number>;
};

/**
 * The small player over the composer while a reply is read aloud: a spinner while the voice is
 * prepared, the time heard (and the whole length once known), pause and resume, Stop, and how
 * far it has got. Not the reply's words: they are on the screen above it. It takes its own
 * touches, as the scroll button does, so a slider or a graph under it never sees them.
 */
export function ReadAloudPlayer({ visible, bottomOffset, lift }: Props) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeS(C), [C]);
  const session = useSyncExternalStore(readAloudSession.subscribe, readAloudSession.get);
  const liftStyle = useBottomLiftStyle(lift);
  const now = useTicking(session?.playingSince != null);

  if (!visible || !session) return null;

  const paused = session.phase === "paused";
  const title = playerTitle(session, t);
  const time = playerTime(readAloudElapsedMs(session, now), session.totalMs);

  return (
    <Animated.View
      style={[s.slot, { bottom: bottomOffset }, lift ? liftStyle : null]}
      testID="read-aloud-player"
    >
      {/* Not one accessible element: VoiceOver must reach Pause and Stop inside it. */}
      <Pressable style={s.card} accessible={false}>
        <View style={s.lead} importantForAccessibility="no-hide-descendants">
          {session.phase === "preparing" ? (
            <ActivityIndicator size="small" color={C.primary} />
          ) : (
            <Icon name="volume" filled size={IconSize.sm} color={C.primary} />
          )}
        </View>
        <View style={s.texts} accessible accessibilityLabel={`${title}, ${time}`}>
          <Text style={s.time} numberOfLines={1} testID="read-aloud-player-time">
            {time}
          </Text>
        </View>
        {session.canPause ? (
          <Pressable
            style={s.button}
            onPress={() => {
              tap();
              if (paused) resumeReadAloud();
              else pauseReadAloud();
            }}
            accessibilityRole="button"
            accessibilityLabel={t(paused ? "chat.read_aloud_resume" : "chat.read_aloud_pause")}
            testID="read-aloud-player-toggle"
          >
            <Icon name={paused ? "play" : "pause"} filled size={IconSize.sm} color={C.text} />
          </Pressable>
        ) : null}
        <Pressable
          style={s.button}
          onPress={() => {
            tap();
            stopReadAloud();
          }}
          accessibilityRole="button"
          accessibilityLabel={t("chat.read_aloud_stop")}
          testID="read-aloud-player-stop"
        >
          <Icon name="close" size={IconSize.sm} color={C.textSecondary} />
        </Pressable>
        {session.progress !== null ? (
          <View style={s.track} importantForAccessibility="no-hide-descendants">
            <View style={[s.fill, { width: `${Math.round(session.progress * 100)}%` }]} />
          </View>
        ) : null}
      </Pressable>
    </Animated.View>
  );
}

/** Now, again every half second while the phone's voice is timed by the clock. */
function useTicking(ticking: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!ticking) return;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(timer);
  }, [ticking]);
  return now;
}

/** "0:04", or "0:04 / 0:12" once the whole length is known. */
function playerTime(elapsedMs: number, totalMs: number | null): string {
  const clock = (ms: number) => {
    const seconds = Math.max(0, Math.floor(ms / 1000));
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  };
  return totalMs === null ? clock(elapsedMs) : `${clock(elapsedMs)} / ${clock(totalMs)}`;
}

function playerTitle(session: ReadAloud, t: (key: string) => string): string {
  if (session.phase === "preparing") return t("chat.read_aloud_preparing");
  if (session.phase === "paused") return t("chat.read_aloud_paused");
  return t("chat.read_aloud_playing");
}

const makeS = (C: Theme) =>
  StyleSheet.create({
    slot: {
      position: "absolute",
      left: Space.md,
      right: Space.md,
      height: READ_ALOUD_PLAYER_HEIGHT,
      zIndex: Layer.header - 5,
    },
    card: {
      flex: 1,
      flexDirection: "row",
      alignItems: "center",
      paddingLeft: Space.sm,
      borderRadius: Radius.lg,
      backgroundColor: C.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
      overflow: "hidden",
      ...shadowElevated(C, "banner"),
    },
    lead: {
      width: IconSize.md,
      alignItems: "center",
    },
    texts: {
      flex: 1,
      marginHorizontal: Space.xs,
    },
    // Digits of one width, so the time does not jiggle as it counts.
    time: {
      ...Type.compact,
      ...Weight.semibold,
      color: C.text,
      fontVariant: ["tabular-nums"],
    },
    button: {
      width: Space.minTouch,
      height: Space.minTouch,
      alignItems: "center",
      justifyContent: "center",
    },
    track: {
      position: "absolute",
      left: 0,
      right: 0,
      bottom: 0,
      height: 2,
      backgroundColor: C.border,
    },
    fill: {
      height: 2,
      backgroundColor: C.primary,
    },
  });
