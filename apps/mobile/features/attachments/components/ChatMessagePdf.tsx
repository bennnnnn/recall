import { useCallback, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { AttachmentPdfViewer } from "@/features/attachments/components/AttachmentPdfViewer";
import { Icon } from "@/ui/icons/Icon";

import { useAuthToken } from "@/contexts/AuthContext";
import { useAttachmentIndexed } from "@/features/attachments/hooks/useAttachmentIndexed";
import { resolveAttachmentUri } from "@/features/attachments/model/attachmentUri";
import { downloadChatAttachment } from "@/features/attachments/model/downloadChatAttachment";
import { libraryActionMessage } from "@/features/attachments/model/attachmentErrors";
import { IconSize } from "@/ui/icons/sizes";
import { Theme, useTheme } from "@/lib/theme";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Type } from "@/lib/type";
import { alertDialog } from "@/ui/overlay/dialogs";

type Props = {
  attachmentId?: string | null;
  localUri?: string | null;
  path?: string | null;
  fileName?: string;
};

/**
 * A sent PDF: one card naming the file, which opens the viewer. No page picture under it: a
 * second bubble showing page 1 repeated the card and read as another message (2026-11-07).
 */
export function ChatMessagePdf({
  attachmentId,
  localUri,
  path,
  fileName = "document.pdf",
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const token = useAuthToken();
  const { indexed, failed: indexFailed } = useAttachmentIndexed(attachmentId);
  const [viewerOpen, setViewerOpen] = useState(false);

  const remoteUri = useMemo(
    () => resolveAttachmentUri({ attachmentId, localUri, path }),
    [attachmentId, localUri, path],
  );

  const handleShare = useCallback(async () => {
    if (!remoteUri) return;
    try {
      await downloadChatAttachment({ uri: remoteUri, token, fileName });
    } catch (error) {
      void alertDialog({
        title: t("common.download_failed"),
        message: libraryActionMessage(error, "chat.pdf_export_failed", t),
      });
    }
  }, [remoteUri, token, fileName, t]);

  if (!remoteUri) return null;

  return (
    <>
      <Pressable
        style={s.card}
        onPress={() => setViewerOpen(true)}
        accessibilityLabel={t("chat.pdf_open_a11y", { fileName })}
        accessibilityRole="button"
      >
        <View style={s.iconWrap}>
          <Icon name="file-text" size={IconSize.md} color={theme.primary} />
        </View>
        <View style={s.meta}>
          <Text style={s.name} numberOfLines={2}>
            {fileName}
          </Text>
          <Text style={s.kind}>
            {indexFailed ? t("chat.file_index_failed") : indexed ? "PDF" : t("chat.file_indexing")}
          </Text>
        </View>
        <Icon name="chevron-right" size={IconSize.sm} color={theme.textTertiary} />
      </Pressable>

      <AttachmentPdfViewer
        visible={viewerOpen}
        onClose={() => setViewerOpen(false)}
        attachmentId={attachmentId}
        localUri={localUri}
        path={path}
        fileName={fileName}
        onShare={handleShare}
      />
    </>
  );
}

const CARD_WIDTH = 280;

function makeStyles(t: Theme) {
  return StyleSheet.create({
    card: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      paddingHorizontal: Space.sm,
      paddingVertical: Space.xs + 2,
      borderRadius: Radius.bubble,
      backgroundColor: t.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      // A fixed width: sized by its content, the end-aligned column of a sent message left
      // a long name nowhere to wrap.
      width: CARD_WIDTH,
      maxWidth: "100%",
    },
    iconWrap: {
      width: 36,
      height: 36,
      borderRadius: Radius.sm,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: t.primaryLight,
    },
    meta: { flex: 1, minWidth: 0 },
    name: { ...Type.label, color: t.text },
    kind: { ...Type.meta, color: t.textTertiary, marginTop: 2 },
  });
}
