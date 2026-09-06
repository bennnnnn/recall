import { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Image, StyleSheet, View } from "react-native";

import { MediaLoadRetry } from "@/components/MediaLoadRetry";
import { useAuthToken } from "@/contexts/AuthContext";
import {
  ensureLocalAttachmentFile,
  getCachedAttachmentFile,
  invalidateCachedAttachmentFile,
} from "@/lib/downloadChatAttachment";
import { resolveAttachmentUri, attachmentRequestHeaders } from "@/lib/attachmentUri";
import { getSessionGeneration } from "@/lib/auth";

export type AttachmentViewerImage = {
  attachmentId?: string | null;
  localUri?: string | null;
  path?: string | null;
  fileName?: string;
  previewUri?: string | null;
};

type Props = {
  item: AttachmentViewerImage;
  active: boolean;
};

export function AttachmentImageStage({ item, active }: Props) {
  const token = useAuthToken();
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [cachedFile, setCachedFile] = useState<{ key: object; uri: string } | null>(null);

  const fileName = item.fileName ?? "image.jpg";
  const remoteUri = useMemo(() => {
    return resolveAttachmentUri({
      attachmentId: item.attachmentId,
      localUri: item.localUri,
      path: item.path,
    });
  }, [item.attachmentId, item.localUri, item.path]);

  const sessionGeneration = getSessionGeneration();
  const fileKey = useMemo(() => ({ remoteUri, sessionGeneration }), [remoteUri, sessionGeneration]);
  const cachedUri = cachedFile?.key === fileKey ? cachedFile.uri : null;

  const displayUri =
    cachedUri ||
    (remoteUri ? getCachedAttachmentFile(remoteUri) : null) ||
    item.localUri ||
    item.previewUri ||
    remoteUri;

  useEffect(() => {
    if (!active) return;
    setFailed(false);
    if (!remoteUri && !item.localUri && !item.previewUri) {
      setFailed(true);
      return;
    }
    if (!remoteUri) return;

    let cancelled = false;
    void ensureLocalAttachmentFile({
      uri: remoteUri,
      token,
      fileName,
    })
      .then((uri) => {
        if (!cancelled) setCachedFile({ key: fileKey, uri });
      })
      .catch(() => {
        // Keep showing previewUri / remote; download/share will surface errors.
      });
    return () => {
      cancelled = true;
    };
  }, [active, remoteUri, item.localUri, item.previewUri, token, fileName, attempt, fileKey]);

  const source = useMemo(() => {
    if (!displayUri) return null;
    const headers = attachmentRequestHeaders(displayUri, token);
    return Object.keys(headers).length ? { uri: displayUri, headers } : { uri: displayUri };
  }, [displayUri, token]);

  if (failed) {
    return (
      <View style={s.stage}>
        <MediaLoadRetry
          onRetry={() => {
            if (remoteUri) invalidateCachedAttachmentFile(remoteUri);
            setCachedFile(null);
            setFailed(false);
            setAttempt((n) => n + 1);
          }}
        />
      </View>
    );
  }

  if (!source) {
    return (
      <View style={s.stage}>
        <ActivityIndicator color="#FFFFFF" size="large" />
      </View>
    );
  }

  return (
    <View style={s.stage}>
      <Image
        key={`${displayUri}:${attempt}`}
        testID="attachment-viewer-image"
        source={source}
        style={s.image}
        resizeMode="contain"
        onError={() => setFailed(true)}
      />
    </View>
  );
}

const s = StyleSheet.create({
  stage: {
    flex: 1,
    width: "100%",
    alignItems: "center",
    justifyContent: "center",
  },
  image: {
    width: "100%",
    height: "100%",
  },
});
