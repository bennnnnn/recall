import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Image,
  Pressable,
  StyleSheet,
  useWindowDimensions,
  View,
} from "react-native";

import { AttachmentImageViewer } from "@/components/AttachmentImageViewer";
import { useAuth } from "@/contexts/AuthContext";
import { getApiUrl } from "@/lib/config";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  attachmentId?: string | null;
  localUri?: string | null;
  path?: string | null;
  fileName?: string;
};

/** ~1/3 screen width, slightly portrait — matches Claude-style chat thumbnails. */
function useThumbnailSize() {
  const { width: screenWidth } = useWindowDimensions();
  const width = Math.round(Math.min(screenWidth * 0.34, 148));
  const height = Math.round(width * 1.28);
  return { width, height };
}

export function ChatMessageImage({ attachmentId, localUri, path, fileName }: Props) {
  const { token } = useAuth();
  const C = useTheme();
  const { width, height } = useThumbnailSize();
  const s = useMemo(() => makeStyles(C, width, height), [C, width, height]);
  const [failed, setFailed] = useState(false);
  const [viewerOpen, setViewerOpen] = useState(false);

  const remoteUri = useMemo(() => {
    if (localUri) return localUri;
    if (attachmentId) return `${getApiUrl()}/attachments/${attachmentId}/file`;
    if (path?.startsWith("http://") || path?.startsWith("https://")) return path;
    if (path?.startsWith("/attachments/")) return `${getApiUrl()}${path}`;
    return null;
  }, [attachmentId, localUri, path]);

  useEffect(() => {
    setFailed(false);
  }, [remoteUri]);

  if (!remoteUri) return null;

  const source =
    token && attachmentId && !localUri
      ? { uri: remoteUri, headers: { Authorization: `Bearer ${token}` } }
      : { uri: remoteUri };

  return (
    <>
      <Pressable
        onPress={() => setViewerOpen(true)}
        accessibilityLabel="View image"
        accessibilityRole="button"
      >
        <View style={s.wrap}>
          {failed ? (
            <View style={[s.preview, s.fallback]}>
              <ActivityIndicator color={C.textTertiary} />
            </View>
          ) : (
            <Image source={source} style={s.preview} resizeMode="cover" />
          )}
        </View>
      </Pressable>

      <AttachmentImageViewer
        visible={viewerOpen}
        onClose={() => setViewerOpen(false)}
        attachmentId={attachmentId}
        localUri={localUri}
        path={path}
        fileName={fileName}
      />
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
    fallback: {
      alignItems: "center",
      justifyContent: "center",
    },
  });
}
