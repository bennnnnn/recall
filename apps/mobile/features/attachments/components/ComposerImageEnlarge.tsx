import { useState } from "react";
import { Pressable, StyleSheet, useWindowDimensions, View } from "react-native";
import { Image, type ImageLoadEventData } from "expo-image";
import Animated, { interpolate, useAnimatedStyle } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Overlay, useOverlayProgress } from "@/ui/overlay/Overlay";

type Size = { width: number; height: number };

/** The largest box with the photo's shape inside `bounds`. */
function fitInside(natural: Size | null, bounds: Size): Size {
  if (!natural || natural.width <= 0 || natural.height <= 0) return bounds;
  const scale = Math.min(bounds.width / natural.width, bounds.height / natural.height);
  return { width: natural.width * scale, height: natural.height * scale };
}

function EnlargedPhoto({ uri, onClose }: { uri: string; onClose: () => void }) {
  const { t } = useTranslation();
  const window = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const progress = useOverlayProgress();
  const [natural, setNatural] = useState<Size | null>(null);
  const bounds = {
    width: window.width - Space.md * 2,
    height: window.height - insets.top - insets.bottom - Space.xl * 2,
  };
  const size = fitInside(natural, bounds);
  // It grows out of the composer's thumbnail rather than popping in.
  const grow = useAnimatedStyle(() => ({
    opacity: progress.value,
    transform: [{ scale: interpolate(progress.value, [0, 1], [0.9, 1]) }],
  }));
  return (
    <View style={styles.center} pointerEvents="box-none">
      <Animated.View style={grow}>
        <Pressable
          onPress={onClose}
          accessibilityRole="button"
          accessibilityLabel={t("common.close")}
          testID="composer-image-enlarged"
        >
          <Image
            source={{ uri }}
            style={[styles.photo, size]}
            contentFit="contain"
            cachePolicy="memory-disk"
            onLoad={(event: ImageLoadEventData) =>
              setNatural({ width: event.source.width, height: event.source.height })
            }
          />
        </Pressable>
      </Animated.View>
    </View>
  );
}

/**
 * The composer's photo, enlarged over the chat so it can be seen before it is sent: a dim
 * page behind it, and a tap anywhere closes it. Not the gallery's viewer (no Download, Share
 * or library actions): the photo is still only a draft.
 */
export function ComposerImageEnlarge({ visible, uri, onClose }: {
  visible: boolean;
  uri: string;
  onClose: () => void;
}) {
  return (
    <Overlay visible={visible} onRequestClose={onClose} scrim="dim" testID="composer-image-enlarge">
      <EnlargedPhoto uri={uri} onClose={onClose} />
    </Overlay>
  );
}

const styles = StyleSheet.create({
  center: { ...StyleSheet.absoluteFill, alignItems: "center", justifyContent: "center" },
  photo: { borderRadius: Radius.bubble },
});
