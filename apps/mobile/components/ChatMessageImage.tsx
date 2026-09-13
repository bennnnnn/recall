import { useEffect, useMemo, useState } from "react";
import {
  Image,
  ImageSourcePropType,
  type ImageLoadEvent,
  Pressable,
  StyleSheet,
  useWindowDimensions,
  View,
} from "react-native";
import { useTranslation } from "react-i18next";
import Animated, { Easing, useAnimatedStyle, useSharedValue, withTiming } from "react-native-reanimated";

import { Icon } from "@/components/Icon";
import { AttachmentImageViewer } from "@/components/AttachmentImageViewer";
import { useAuthToken } from "@/contexts/AuthContext";
import { resolveAttachmentUri, attachmentRequestHeaders } from "@/lib/attachmentUri";
import { ensureLocalAttachmentFile } from "@/lib/downloadChatAttachment";
import { fitAttachmentImage, type ImageSize } from "@/lib/attachmentImageSize";
import { motionMs, useReduceMotion } from "@/lib/motion";
import { Theme, useTheme } from "@/lib/theme";

const AnimatedImage = Animated.createAnimatedComponent(Image);
const REVEAL_DURATION_MS = 280;
const REVEAL_BLUR_RADIUS = 16;

type Props = {
  attachmentId?: string | null;
  localUri?: string | null;
  path?: string | null;
  fileName?: string;
  /**
   * Soft blur→sharp "develop" reveal. Default on for generated/assistant
   * images; user attach previews should pass false so a post-reply refetch
   * doesn't flash gray/blur again.
   */
  animatedReveal?: boolean;
  /** Show the complete user attachment instead of cropping its contents. */
  previewFit?: "cover" | "contain";
  /** Override the default ~1/3-screen thumb. Used by the multi-image strip. */
  width?: number;
  height?: number;
  /** If set, tap opens this instead of the built-in single-image viewer. */
  onOpen?: () => void;
};

/** ~1/3 screen width, slightly portrait — matches Claude-style chat thumbnails. */
export function useThumbnailSize() {
  const { width: screenWidth } = useWindowDimensions();
  const width = Math.round(Math.min(screenWidth * 0.34, 148));
  const height = Math.round(width * 1.28);
  return { width, height };
}

type RevealingImageProps = {
  source: ImageSourcePropType;
  style: ReturnType<typeof makeStyles>["preview"];
  layerStyle: ReturnType<typeof makeStyles>["layer"];
  onError: () => void;
  onLoad: (event: ImageLoadEvent) => void;
  reduceMotion: boolean;
  previewFit: "cover" | "contain";
};

/** Owns the blur→sharp reveal animation for one image load. Keyed by URI at
 * the call site so a different image gets a fresh shared value on mount
 * instead of an imperative reset. */
function RevealingImage({
  source,
  style,
  layerStyle,
  onError,
  onLoad,
  reduceMotion,
  previewFit,
}: RevealingImageProps) {
  const reveal = useSharedValue(reduceMotion ? 1 : 0);
  const sharpStyle = useAnimatedStyle(() => ({ opacity: reveal.value }));
  const blurStyle = useAnimatedStyle(() => ({ opacity: 1 - reveal.value }));

  const handleLoad = (event: ImageLoadEvent) => {
    onLoad(event);
    // Reanimated shared values are designed to be mutated from any JS-thread
    // callback, including a plain event handler like this one — this isn't
    // the kind of render-purity violation the immutability rule exists to
    // catch. The rule doesn't yet recognize SharedValue as an exempt
    // mutable-ref type (a known gap for Reanimated under React Compiler).
    // eslint-disable-next-line react-hooks/immutability
    reveal.value = withTiming(1, {
      duration: motionMs(REVEAL_DURATION_MS, reduceMotion),
      easing: Easing.out(Easing.ease),
    });
  };

  if (reduceMotion) {
    return (
      <AnimatedImage
        source={source}
        style={[style, layerStyle]}
        resizeMode={previewFit}
        onError={onError}
        onLoad={onLoad}
      />
    );
  }

  return (
    <>
      {/* Blurred layer fades out as the sharp layer fades in — a soft
          "develop" reveal rather than a hard pop once decoded. */}
      <AnimatedImage
        source={source}
        style={[style, layerStyle, blurStyle]}
        resizeMode={previewFit}
        blurRadius={REVEAL_BLUR_RADIUS}
      />
      <AnimatedImage
        source={source}
        style={[style, layerStyle, sharpStyle]}
        resizeMode={previewFit}
        onLoad={handleLoad}
        onError={onError}
      />
    </>
  );
}

export function ChatMessageImage(props: Props) {
  const uri = resolveAttachmentUri({ attachmentId: props.attachmentId, localUri: props.localUri, path: props.path });
  if (!uri) return null;
  // A new source owns new load/error state; a late event from the old image
  // cannot resize the next attachment, including local-to-remote replacement.
  return <ChatMessageImageContent key={props.localUri || uri} {...props} remoteUri={uri} />;
}

function ChatMessageImageContent({
  attachmentId,
  localUri,
  path,
  fileName,
  animatedReveal = true,
  previewFit = "cover",
  width: widthOverride,
  height: heightOverride,
  onOpen,
  remoteUri,
}: Props & { remoteUri: string }) {
  const { t } = useTranslation();
  const token = useAuthToken();
  const C = useTheme();
  const reduceMotion = useReduceMotion();
  const thumb = useThumbnailSize();
  const maxWidth = widthOverride ?? thumb.width;
  const maxHeight = heightOverride ?? thumb.height;
  const [decodedSize, setDecodedSize] = useState<ImageSize | null>(null);
  const fitted = previewFit === "contain" && decodedSize
    ? fitAttachmentImage(decodedSize, { width: maxWidth, height: maxHeight })
    : null;
  const { width, height } = fitted ?? { width: maxWidth, height: maxHeight };
  const onLoad = (event: ImageLoadEvent) => {
    if (previewFit !== "contain") return;
    const size = event.nativeEvent.source;
    if (fitAttachmentImage(size, { width: maxWidth, height: maxHeight })) {
      setDecodedSize({ width: size.width, height: size.height });
    }
  };
  const s = useMemo(() => makeStyles(C, width, height), [C, width, height]);
  const [failed, setFailed] = useState(false);
  const [viewerOpen, setViewerOpen] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [remoteUri, token]);

  // Warm a local file:// copy so fullscreen opens instantly and download/share
  // don't hit createDownloadResumable (auth URLs fail there).
  useEffect(() => {
    if (!remoteUri || localUri?.startsWith("file://")) return;
    let cancelled = false;
    void ensureLocalAttachmentFile({
      uri: remoteUri,
      token,
      fileName: fileName ?? "image.jpg",
    }).catch(() => {
      if (cancelled) return;
    });
    return () => {
      cancelled = true;
    };
  }, [remoteUri, localUri, token, fileName]);

  if (!remoteUri) return null;

  const headers = attachmentRequestHeaders(remoteUri, token);
  const source = Object.keys(headers).length ? { uri: remoteUri, headers } : { uri: remoteUri };

  // Local file:// previews (and user attach thumbs) stay sharp — no blur
  // "develop" reveal that restarts when a silent refetch swaps the URI.
  const usePlainPreview = Boolean(localUri) || !animatedReveal;

  return (
    <>
      <Pressable
        onPress={() => {
          if (onOpen) {
            onOpen();
            return;
          }
          setViewerOpen(true);
        }}
        accessibilityLabel={t("chat.image_view_a11y")}
        accessibilityRole="button"
      >
        <View style={s.wrap} testID="chat-image-frame">
          {failed ? (
            // Static broken-image mark — never a spinner (that read as
            // "still generating" when the attachment 404'd).
            <View
              style={[s.preview, s.fallback]}
              accessibilityLabel={t("chat.image_unavailable_a11y")}
            >
              <Icon name="image-outline" size={28} color={C.textTertiary} />
            </View>
          ) : usePlainPreview ? (
            <Image
              source={localUri ? { uri: localUri } : source}
              style={s.preview}
              resizeMode={previewFit}
              onError={() => setFailed(true)}
              onLoad={onLoad}
              testID="chat-image-preview"
            />
          ) : (
            <RevealingImage
              key={remoteUri}
              source={source}
              style={s.preview}
              layerStyle={s.layer}
              onError={() => setFailed(true)}
              reduceMotion={reduceMotion}
              previewFit={previewFit}
              onLoad={onLoad}
            />
          )}
        </View>
      </Pressable>

      {onOpen ? null : (
        <AttachmentImageViewer
          visible={viewerOpen}
          onClose={() => setViewerOpen(false)}
          attachmentId={attachmentId}
          localUri={localUri}
          path={path}
          fileName={fileName}
          previewUri={remoteUri}
        />
      )}
    </>
  );
}

function makeStyles(C: Theme, width: number, height: number) {
  return StyleSheet.create({
    wrap: {
      width,
      height,
      borderRadius: 22,
      overflow: "hidden",
      backgroundColor: C.surfaceAlt,
    },
    preview: {
      width: "100%",
      height: "100%",
    },
    layer: {
      position: "absolute",
      top: 0,
      left: 0,
    },
    fallback: {
      alignItems: "center",
      justifyContent: "center",
    },
  });
}
