import { memo, useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Image, StyleSheet, View } from "react-native";

import { Icon } from "@/components/Icon";
import { useAuthToken } from "@/contexts/AuthContext";
import { resolveAttachmentUri } from "@/lib/attachmentUri";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  /** Attachment id — used to build the authenticated /file URL. */
  attachmentId: string;
  /** Optional already-resolved URL (presigned). Falls back to /file. */
  downloadUrl?: string | null;
  /** Square thumbnail size in px. */
  size?: number;
};

const LOAD_TIMEOUT_MS = 10_000;

export { LOAD_TIMEOUT_MS };

function GalleryThumbnailBase({ attachmentId, downloadUrl, size = 1 }: Props) {
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const token = useAuthToken();
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const uri = resolveAttachmentUri({ attachmentId, path: downloadUrl })!;

  // resolveAttachmentUri prefers /file when attachmentId is set. That
  // endpoint always needs Bearer — including when the list also returned a
  // presigned R2 URL (ChatMessageImage sends auth the same way).
  const source = token
    ? { uri, headers: { Authorization: `Bearer ${token}` } }
    : { uri };

  const dimension = { width: size, height: size };

  const clearLoadTimer = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  // Fallback: if onLoad doesn't fire within the timeout, mark as failed.
  // React Native's Image doesn't always call onError for corrupt/missing data.
  useEffect(() => {
    setFailed(false);
    setLoaded(false);
    clearLoadTimer();
    timerRef.current = setTimeout(() => {
      setFailed(true);
    }, LOAD_TIMEOUT_MS);
    return clearLoadTimer;
  }, [attachmentId, uri]);

  return (
    <View style={[s.wrap, dimension]}>
      {failed ? (
        <View style={[s.fallback, dimension]}>
          <Icon name="image-outline" size={24} color={C.textTertiary} />
        </View>
      ) : (
        <>
          {!loaded ? (
            <View style={[s.loading, dimension]} testID="gallery-thumb-loading">
              <ActivityIndicator size="small" color={C.textTertiary} />
            </View>
          ) : null}
          <Image
            key={uri}
            testID="gallery-thumb-image"
            source={source}
            style={[dimension, s.image]}
            resizeMode="cover"
            onLoad={() => {
              clearLoadTimer();
              setLoaded(true);
            }}
            onError={() => {
              clearLoadTimer();
              setFailed(true);
            }}
          />
        </>
      )}
    </View>
  );
}

export const GalleryThumbnail = memo(GalleryThumbnailBase);

function makeStyles(C: Theme) {
  return StyleSheet.create({
    wrap: {
      borderRadius: 10,
      overflow: "hidden",
      backgroundColor: C.surface,
    },
    image: {
      backgroundColor: C.surface,
    },
    loading: {
      position: "absolute",
      alignItems: "center",
      justifyContent: "center",
      zIndex: 1,
    },
    fallback: {
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: C.surface,
    },
  });
}
