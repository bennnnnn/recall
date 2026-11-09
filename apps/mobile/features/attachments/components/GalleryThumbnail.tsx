import { memo, useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";
import { Image } from "expo-image";

import { Icon } from "@/ui/icons/Icon";
import { MediaLoadRetry } from "@/components/MediaLoadRetry";
import { useAuthToken } from "@/contexts/AuthContext";
import { attachmentRecordExists } from "@/lib/api";
import {
  attachmentRequestHeaders,
  attachmentThumbWidth,
  resolveAttachmentUri,
} from "@/features/attachments/model/attachmentUri";
import { Theme, useTheme } from "@/lib/theme";
import { IconSize } from "@/ui/icons/sizes";
import { Radius } from "@/lib/radius";
import { useLatestRef } from "@/lib/latestRef";

type Props = {
  /** Attachment id — used to build the authenticated /file URL. */
  attachmentId: string;
  /** Square thumbnail size in px. */
  size?: number;
  /** Called once when the server confirms the record is gone (GET /url 404). */
  onMissing?: (attachmentId: string) => void;
};

const LOAD_TIMEOUT_MS = 20_000;
const RETRY_LABEL_MIN_SIZE = 80;

export { LOAD_TIMEOUT_MS };

function GalleryThumbnailBase({
  attachmentId,
  size = 1,
  onMissing,
}: Props) {
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const token = useAuthToken();
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const settledRef = useRef(false);
  const missingNotifiedRef = useRef(false);
  const probeGenRef = useRef(0);

  // 2x for sharp tiles, capped at what the API serves (a tablet tile asks for less than 2x).
  const uri = resolveAttachmentUri({
    attachmentId,
    width: attachmentThumbWidth(size * 2),
  })!;
  // The API's /file needs the Bearer token; the helper sends it to the API's origin only.
  const source = { uri, headers: attachmentRequestHeaders(uri, token) };

  const dimension = { width: size, height: size };
  const compact = size < RETRY_LABEL_MIN_SIZE;

  const onMissingRef = useLatestRef(onMissing);
  const tokenRef = useLatestRef(token);

  const clearLoadTimer = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
  };

  // Fallback for corrupt/missing data, which doesn't always call onError: no progress for the
  // timeout marks the load failed. The clock restarts as it starts and with every chunk: counted
  // from mount, a tile still arriving on a slow connection turned into Retry at 20 s.
  const armLoadTimer = () => {
    if (settledRef.current) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setFailed(true), LOAD_TIMEOUT_MS);
  };

  const reportMissing = () => {
    if (missingNotifiedRef.current) return;
    missingNotifiedRef.current = true;
    onMissingRef.current?.(attachmentId);
  };

  const dropIfGone = async () => {
    const auth = tokenRef.current;
    if (!auth) return;
    const gen = ++probeGenRef.current;
    const exists = await attachmentRecordExists(auth, attachmentId);
    if (gen !== probeGenRef.current) return;
    if (exists === false) reportMissing();
  };

  useEffect(() => {
    setFailed(false);
    setLoaded(false);
    missingNotifiedRef.current = false;
    probeGenRef.current += 1;
    settledRef.current = false;
    armLoadTimer();
    return clearLoadTimer;
  }, [attachmentId, uri, attempt]);

  return (
    <View style={[s.wrap, dimension]}>
      {failed ? (
        <View style={[s.fallback, dimension]}>
          {compact ? null : <Icon name="image" size={IconSize.md} color={C.textTertiary} />}
          <MediaLoadRetry
            compact={compact}
            onRetry={() => setAttempt((n) => n + 1)}
          />
        </View>
      ) : (
        <>
          {!loaded ? (
            <View style={[s.loading, dimension]} testID="gallery-thumb-loading">
              <ActivityIndicator size="small" color={C.textTertiary} />
            </View>
          ) : null}
          <Image
            key={`${uri}:${attempt}`}
            testID="gallery-thumb-image"
            source={source}
            style={[dimension, s.image]}
            contentFit="cover"
            cachePolicy="memory-disk"
            onLoadStart={armLoadTimer}
            onProgress={armLoadTimer}
            onLoad={() => {
              settledRef.current = true;
              clearLoadTimer();
              setLoaded(true);
            }}
            onError={() => {
              settledRef.current = true;
              clearLoadTimer();
              setFailed(true);
              void dropIfGone();
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
      borderRadius: Radius.sm,
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
