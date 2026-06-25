import { Share } from 'react-native';

import { Message } from '@/lib/api';

function buildTranscript(title: string | null, messages: Message[]): string {
  const header = `# ${title?.trim() || 'Conversation'}\n\n`;
  const body = messages
    .filter((m) => m.role !== 'system')
    .map((m) => `**${m.role === 'user' ? 'You' : 'Recall'}:**\n${m.content}`)
    .join('\n\n');
  return header + body;
}

/** Share/export a conversation as a markdown transcript via the native sheet. */
export async function shareConversation(title: string | null, messages: Message[]): Promise<void> {
  if (!messages.length) return;
  try {
    await Share.share({ message: buildTranscript(title, messages) });
  } catch {
    // user cancelled or share is unavailable — ignore
  }
}
