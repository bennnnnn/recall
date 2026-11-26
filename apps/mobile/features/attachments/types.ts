import type { Page } from "@/lib/api/types";

export type AttachmentListItem = {
  id: string;
  content_type: string;
  size_bytes: number;
  download_url: string;
  source: "upload" | "generated";
  created_at: string;
  chat_id?: string | null;
  message_id?: string | null;
  original_filename?: string | null;
  chat_title?: string | null;
  /** Text the user pasted into the composer (the API's record): sent again, it is a paste. */
  pasted?: boolean;
};

export type AttachmentListResponse = Page<AttachmentListItem>;
