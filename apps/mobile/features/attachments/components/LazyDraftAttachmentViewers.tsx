/**
 * What shows an attachment picked in the composer, before it is sent: the photo enlarged
 * over the chat, the PDF reader and the text reader. Each loads and mounts the first time
 * it is opened, not with the chat screen (the PDF reader brings pdf.js and the file system).
 */
import type { ComponentProps } from "react";

import type { ComposerImageEnlarge } from "@/features/attachments/components/ComposerImageEnlarge";
import type { AttachmentPdfViewer } from "@/features/attachments/components/AttachmentPdfViewer";
import type { AttachmentTextViewer } from "@/features/attachments/components/AttachmentTextViewer";
import { lazyOverlay } from "@/ui/overlay/lazyOverlay";

export const LazyAttachmentPdfViewer = lazyOverlay<ComponentProps<typeof AttachmentPdfViewer>>(() =>
  import("@/features/attachments/components/AttachmentPdfViewer").then((m) => ({
    default: m.AttachmentPdfViewer,
  })),
);

export const LazyAttachmentTextViewer = lazyOverlay<ComponentProps<typeof AttachmentTextViewer>>(() =>
  import("@/features/attachments/components/AttachmentTextViewer").then((m) => ({
    default: m.AttachmentTextViewer,
  })),
);

export const LazyComposerImageEnlarge = lazyOverlay<ComponentProps<typeof ComposerImageEnlarge>>(() =>
  import("@/features/attachments/components/ComposerImageEnlarge").then((m) => ({
    default: m.ComposerImageEnlarge,
  })),
);
