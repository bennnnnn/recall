import { request } from "@/lib/api/client";
import type {
  Chat,
  ChatList,
  Feedback,
  Message,
  MessagePage,
} from "@/lib/api/types";

function normalizeMessagePage(data: MessagePage | Message[]): MessagePage {
  if (Array.isArray(data)) {
    return { messages: data, has_more: false };
  }
  return data;
}

async function listMessages(
  token: string,
  chatId: string,
  opts?: { limit?: number; before?: string },
): Promise<MessagePage> {
  const params = new URLSearchParams();
  if (opts?.limit != null) params.set("limit", String(opts.limit));
  if (opts?.before) params.set("before", opts.before);
  const qs = params.toString();
  const data = await request<MessagePage | Message[]>(
    `/chats/${chatId}/messages${qs ? `?${qs}` : ""}`,
    token,
  );
  return normalizeMessagePage(data);
}

export const chatsApi = {
  createChat: (
    token: string,
    model = "auto",
    projectId?: string,
    quizMode?: "exam" | "chat",
  ) =>
    request<Chat>("/chats", token, {
      method: "POST",
      body: JSON.stringify({
        model,
        ...(projectId ? { project_id: projectId } : {}),
        ...(quizMode ? { quiz_mode: quizMode } : {}),
      }),
    }),
  getChat: (token: string, chatId: string) =>
    request<Chat>(`/chats/${chatId}`, token),
  renameChat: (token: string, chatId: string, title: string) =>
    request<Chat>(`/chats/${chatId}`, token, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),
  setPin: (token: string, chatId: string, pinned: boolean) =>
    request<Chat>(`/chats/${chatId}/pin`, token, {
      method: "PATCH",
      body: JSON.stringify({ pinned }),
    }),
  setArchive: (token: string, chatId: string, archived: boolean) =>
    request<Chat>(`/chats/${chatId}/archive`, token, {
      method: "PATCH",
      body: JSON.stringify({ archived }),
    }),
  deleteChat: (token: string, chatId: string) =>
    request<void>(`/chats/${chatId}`, token, { method: "DELETE" }),
  deleteChatIfEmpty: async (token: string, chatId: string) => {
    const page = normalizeMessagePage(
      await request<MessagePage | Message[]>(
        `/chats/${chatId}/messages?limit=20`,
        token,
      ),
    );
    const hasAssistant = page.messages.some((m) => m.role === "assistant");
    if (page.messages.length === 0 || !hasAssistant) {
      await request<void>(`/chats/${chatId}`, token, { method: "DELETE" });
    }
  },
  listChats: (token: string) => request<ChatList>("/chats", token),
  listMessages,
  listAllMessages: async (token: string, chatId: string): Promise<Message[]> => {
    const batch = 100;
    let before: string | undefined;
    let hasMore = true;
    let all: Message[] = [];
    while (hasMore) {
      const page = await listMessages(token, chatId, {
        limit: batch,
        before,
      });
      if (!before) {
        all = page.messages;
      } else {
        all = [...page.messages, ...all];
      }
      hasMore = page.has_more;
      if (hasMore && page.messages.length > 0) {
        before = page.messages[0].id;
      } else {
        break;
      }
    }
    return all;
  },
  setMessageFeedback: (
    token: string,
    chatId: string,
    messageId: string,
    feedback: Feedback,
  ) =>
    request<Message>(`/chats/${chatId}/messages/${messageId}/feedback`, token, {
      method: "PATCH",
      body: JSON.stringify({ feedback }),
    }),
};
