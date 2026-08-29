import { Platform, Share } from "react-native";

import { conversationTranscript } from "@/lib/chatTranscript";
import { Message } from "@/lib/api";
import { isShareCancelled } from "@/lib/exportPdf";

/** Open the OS share sheet (Messages, Mail, Files, …). */
export async function presentShareSheet(options: {
  message: string;
  title?: string | null;
}): Promise<void> {
  const message = options.message.trim();
  if (!message) {
    throw new Error("share_empty");
  }
  const title = options.title?.trim() || undefined;
  try {
    await Share.share(
      { message, ...(title ? { title } : {}) },
      Platform.OS === "ios"
        ? { subject: title }
        : { dialogTitle: title },
    );
  } catch (error) {
    if (isShareCancelled(error)) return;
    throw error;
  }
}

/** Share/export a conversation as a markdown transcript via the native sheet. */
export async function shareConversation(
  title: string | null,
  messages: Message[],
): Promise<void> {
  const transcript = conversationTranscript(title, messages);
  await presentShareSheet({
    message: transcript,
    title: title?.trim() || undefined,
  });
}
