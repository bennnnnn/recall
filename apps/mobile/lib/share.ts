import { Share } from "react-native";

import { conversationTranscript } from "@/lib/chatTranscript";
import { Message } from "@/lib/api";

/** Share/export a conversation as a markdown transcript via the native sheet. */
export async function shareConversation(
  title: string | null,
  messages: Message[],
): Promise<void> {
  if (!messages.length) return;
  try {
    await Share.share({ message: conversationTranscript(title, messages) });
  } catch {
    // user cancelled or share is unavailable — ignore
  }
}
