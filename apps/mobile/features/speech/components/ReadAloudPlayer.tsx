import { useMemo, useSyncExternalStore } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { Pressable } from "react-native-gesture-handler";
import Animated, { type SharedValue } from "react-native-reanimated";
import { useTranslation } from "react-i18next";

import { stopReadingAloud } from "@/features/speech/model/pronunciation";
import {
  pauseReadAloud,
  readAloudSession,
  resumeReadAloud,
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
export const READ_ALOUD_PLAYER_HEIGHT = 56;

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
 * The small player over the composer while a reply is read aloud: what it reads, a spinner
 * while the voice is prepared (a cloud voice takes a few seconds), pause and resume, Stop, and
 * how far it has got. It takes its own touches, as the scroll button does, so a slider or a
 * graph under it never sees them.
 */
export function ReadAloudPlayer({ visible, bottomOffset, lift }: Props) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeS(C), [C]);
  const session = useSyncExternalStore(readAloudSession.subscribe, readAloudSession.get);
  const liftStyle = useBottomLiftStyle(lift);

  if (!visible || !session) return null;

  const paused = session.phase === "paused";
  const title = playerTitle(session, t);

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
        <View style={s.texts} accessible accessibilityLabel={`${title}. ${session.preview}`}>
          <Text style={s.title} numberOfLines={1}>
            {title}
          </Text>
          <Text style={s.preview} numberOfLines={1}>
            {session.preview}
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
            stopReadingAloud();
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
    title: {
      ...Type.caption,
      ...Weight.semibold,
      color: C.text,
    },
    preview: {
      ...Type.caption,
      color: C.textSecondary,
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
