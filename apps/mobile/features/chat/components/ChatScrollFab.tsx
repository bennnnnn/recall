import { useMemo } from "react";
import { StyleSheet, View } from "react-native";
import { Pressable } from "react-native-gesture-handler";
import Animated, { type SharedValue } from "react-native-reanimated";
import { Icon } from "@/ui/icons/Icon";
import { useTranslation } from "react-i18next";

import { CountBadge } from "@/ui/feedback/CountBadge";
import { Theme, useTheme } from "@/lib/theme";
import { formatScrollAwayBadge } from "@/features/chat/model/scrollLogic";
import { tap } from "@/lib/haptics";
import { IconSize } from "@/ui/icons/sizes";
import { Layer } from "@/lib/layer";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { useBottomLiftStyle } from "@/ui/hooks/useBottomLiftStyle";

/** The round button as drawn. */
export const SCROLL_FAB_SIZE = Space.minTouch;
/**
 * The square the button owns around it. A tap near the circle presses the button instead of
 * landing on the message under it (a calculator card's slider moved when the button was tapped).
 */
export const SCROLL_FAB_TARGET = SCROLL_FAB_SIZE + Space.xs * 2;

type Props = {
  visible: boolean;
  bottomOffset: number;
  /** Rides the keyboard with the composer, frame by frame. */
  lift?: SharedValue<number>;
  scrollAwayCount: number;
  onPress: () => void;
};

/**
 * The scroll-to-latest button over the end of the chat. It floats over the messages, so it
 * takes every touch in its own square: the slot is the size of that square (no full-width
 * strip that passes touches on), and the press is a native gesture-handler button, so a
 * gesture in the content under it (a slider, a graph's pan) never sees the touch, on iOS or
 * on Android, where the gesture handler finds its own target.
 */
export function ChatScrollFab({ visible, bottomOffset, lift, scrollAwayCount, onPress }: Props) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeS(C), [C]);
  const liftStyle = useBottomLiftStyle(lift);
  const badgeLabel = formatScrollAwayBadge(scrollAwayCount);

  if (!visible) return null;

  return (
    <Animated.View
      style={[s.slot, { bottom: bottomOffset - Space.xs }, lift ? liftStyle : null]}
      testID="chat-scroll-fab"
    >
      <Pressable
        style={s.target}
        onPress={() => {
          tap();
          onPress();
        }}
        accessibilityRole="button"
        accessibilityLabel={t("chat.scroll_to_latest")}
        testID="chat-scroll-fab-button"
      >
        <View style={s.button} pointerEvents="none">
          <Icon name="chevron-down" size={IconSize.md} color={C.text} />
          {badgeLabel ? (
            <CountBadge count={scrollAwayCount} max={9} style={s.badge} />
          ) : null}
        </View>
      </Pressable>
    </Animated.View>
  );
}

const makeS = (C: Theme) =>
  StyleSheet.create({
    slot: {
      position: "absolute",
      left: "50%",
      marginLeft: -SCROLL_FAB_TARGET / 2,
      width: SCROLL_FAB_TARGET,
      height: SCROLL_FAB_TARGET,
      zIndex: Layer.header - 5,
    },
    target: {
      width: SCROLL_FAB_TARGET,
      height: SCROLL_FAB_TARGET,
      alignItems: "center",
      justifyContent: "center",
    },
    button: {
      width: SCROLL_FAB_SIZE,
      height: SCROLL_FAB_SIZE,
      borderRadius: Radius.full,
      backgroundColor: C.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
      alignItems: "center",
      justifyContent: "center",
    },
    badge: {
      position: "absolute",
      top: -4,
      right: -4,
    },
  });
