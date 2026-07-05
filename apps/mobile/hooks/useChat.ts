import { useCallback, useEffect, useRef, useState } from "react";
import { chatWebSocketUrl, Message, SearchSource } from "@/lib/api";
import { streamChatEditSse, streamChatMessageSse, streamChatRegenerateSse, type ChatSsePayload } from "@/lib/chatSse";
import { clientGeoWsFields, type ClientGeo } from "@/lib/clientGeo";
import { getDeviceTimezone } from "@/lib/deviceTimezone";
import { isVocabQuizAnswer } from "@/lib/parseVocabQuiz";
import {
  applyStreamEndModel,
  buildDoneMergeInput,
  mergeDoneIntoMessages,
  parseChatWsPayload,
} from "@/lib/chatSocketReduce";
import {
  publishStreamingDraft,
  type StreamingDraft,
} from "@/lib/streamingDraftStore";
import {
  popLastAssistantMessage,
  restoreAssistantMessage,
} from "@/lib/chatRegenerateLogic";

const CONNECT_TIMEOUT_MS = 8000;

export type { StreamingDraft };

type UseChatOptions = {
  /** Called with the new title when the server sends one after first reply */
  onFirstReply?: () => void;
  /** Called when the server or socket reports an error */
  onError?: (message: string, code?: string) => void;
  /** Refresh lists/reminders after chat may have synced todos */
  onTodosSync?: () => void;
};

export function useChat(
  token: string | null,
  chatId: string | null,
  options: UseChatOptions = {},
) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [sendingMessageId, setSendingMessageId] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const connectingRef = useRef<Promise<void> | null>(null);
  const preferSseRef = useRef(false);
  const assistantBuffer = useRef("");
  const reasoningBuffer = useRef("");
  const streamingDraftRef = useRef<StreamingDraft | null>(null);
  const draftRafRef = useRef<number | null>(null);
  const streamingRef = useRef(false);
  const finalizingRef = useRef(false);
  /** Prior assistant reply kept until regenerate succeeds or is rolled back. */
  const regenerateBackupRef = useRef<Message | null>(null);

  const flushStreamingDraft = useCallback(() => {
    draftRafRef.current = null;
    publishStreamingDraft(streamingDraftRef.current);
  }, []);

  const updateStreamingDraft = useCallback(
    (draft: StreamingDraft | null) => {
      streamingDraftRef.current = draft;
      if (draft === null) {
        if (draftRafRef.current != null) {
          cancelAnimationFrame(draftRafRef.current);
          draftRafRef.current = null;
        }
        publishStreamingDraft(null);
        return;
      }
      if (draftRafRef.current == null) {
        draftRafRef.current = requestAnimationFrame(flushStreamingDraft);
      }
    },
    [flushStreamingDraft],
  );
  const firstReplyRef = useRef(false);
  const onFirstReplyRef = useRef(options.onFirstReply);
  const onErrorRef = useRef(options.onError);
  const onTodosSyncRef = useRef(options.onTodosSync);
  onFirstReplyRef.current = options.onFirstReply;
  onErrorRef.current = options.onError;
  onTodosSyncRef.current = options.onTodosSync;

  const reportError = useCallback((message: string, code?: string) => {
    onErrorRef.current?.(message, code);
  }, []);

  const clearStreamingBubble = useCallback(() => {
    updateStreamingDraft(null);
    setFinalizing(false);
    setMessages((prev) => prev.filter((m) => m.id !== "streaming"));
  }, [updateStreamingDraft]);

  const restoreRegenerateBackup = useCallback(() => {
    const backup = regenerateBackupRef.current;
    regenerateBackupRef.current = null;
    clearStreamingBubble();
    setStreaming(false);
    setFinalizing(false);
    streamingRef.current = false;
    if (backup) {
      setMessages((prev) => restoreAssistantMessage(prev, backup));
    }
  }, [clearStreamingBubble]);

  const appendStreamingPlaceholder = useCallback(() => {
    setMessages((prev) => {
      if (prev.some((m) => m.id === "streaming")) return prev;
      return [
        ...prev,
        {
          id: "streaming",
          renderKey: `stream-${Date.now()}`,
          role: "assistant" as const,
          content: "",
          model: null,
          created_at: new Date().toISOString(),
        },
      ];
    });
  }, []);

  // Keep streamingRef in sync so onclose/onerror closures always see fresh value
  useEffect(() => {
    streamingRef.current = streaming;
  }, [streaming]);

  useEffect(() => {
    finalizingRef.current = finalizing;
  }, [finalizing]);

  useEffect(() => {
    return () => {
      if (draftRafRef.current != null) {
        cancelAnimationFrame(draftRafRef.current);
      }
      wsRef.current?.close();
    };
  }, []);

  // Close and reset socket when chat changes
  useEffect(() => {
    wsRef.current?.close();
    wsRef.current = null;
    connectingRef.current = null;
    preferSseRef.current = false;
    assistantBuffer.current = "";
    reasoningBuffer.current = "";
    firstReplyRef.current = false;
    regenerateBackupRef.current = null;
    updateStreamingDraft(null);
    setStreaming(false);
    setFinalizing(false);
    setSendingMessageId(null);
  }, [chatId, updateStreamingDraft]);

  const handleChatPayload = useCallback(
    (payload: ChatSsePayload) => {
      if (payload.type === "start") {
        setSendingMessageId(null);
        setFinalizing(false);
        setStreaming(true);
        streamingRef.current = true;
        assistantBuffer.current = "";
        reasoningBuffer.current = "";
        updateStreamingDraft({ content: "" });
        appendStreamingPlaceholder();
      }

      if (payload.type === "status" && typeof payload.phase === "string") {
        updateStreamingDraft({
          content: assistantBuffer.current,
          search_sources: streamingDraftRef.current?.search_sources,
          status: payload.phase,
          reasoning: reasoningBuffer.current || undefined,
        });
      }

      if (payload.type === "reasoning" && typeof payload.content === "string") {
        reasoningBuffer.current += payload.content;
        updateStreamingDraft({
          content: assistantBuffer.current,
          search_sources: streamingDraftRef.current?.search_sources,
          status: streamingDraftRef.current?.status,
          reasoning: reasoningBuffer.current,
        });
      }

      if (payload.type === "token") {
        assistantBuffer.current += payload.content ?? "";
        updateStreamingDraft({
          content: assistantBuffer.current,
          search_sources: streamingDraftRef.current?.search_sources,
          status: undefined,
          reasoning: reasoningBuffer.current || undefined,
        });
      }

      if (payload.type === "stream_end") {
        setFinalizing(true);
        if (typeof payload.resolved_model === "string" && payload.resolved_model) {
          setMessages((prev) => applyStreamEndModel(prev, payload.resolved_model));
        }
      }

      if (payload.type === "done") {
        regenerateBackupRef.current = null;
        setStreaming(false);
        setFinalizing(false);
        streamingRef.current = false;
        assistantBuffer.current = "";
        reasoningBuffer.current = "";
        const draft = streamingDraftRef.current;
        updateStreamingDraft(null);
        setMessages((prev) =>
          mergeDoneIntoMessages(prev, buildDoneMergeInput(payload, draft)),
        );
        if (!firstReplyRef.current) {
          firstReplyRef.current = true;
          onFirstReplyRef.current?.();
        }
        if (payload.todos_sync === "1") {
          onTodosSyncRef.current?.();
          setTimeout(() => onTodosSyncRef.current?.(), 2500);
        }
      }

      if (payload.type === "error") {
        setSendingMessageId(null);
        setStreaming(false);
        setFinalizing(false);
        streamingRef.current = false;
        assistantBuffer.current = "";
        reasoningBuffer.current = "";
        if (regenerateBackupRef.current) {
          restoreRegenerateBackup();
        } else {
          clearStreamingBubble();
        }
        reportError(
          payload.message ?? "Something went wrong. Try again.",
          typeof payload.code === "string" ? payload.code : undefined,
        );
      }
    },
    [
      appendStreamingPlaceholder,
      clearStreamingBubble,
      restoreRegenerateBackup,
      reportError,
      updateStreamingDraft,
    ],
  );

  const connect = useCallback((): Promise<void> => {
    if (!token || !chatId) return Promise.resolve();
    if (preferSseRef.current) return Promise.resolve();
    if (wsRef.current?.readyState === WebSocket.OPEN) return Promise.resolve();
    // Reuse an in-flight connection so concurrent callers don't tear each other down
    if (connectingRef.current) return connectingRef.current;

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    const connectPromise = new Promise<void>((resolve, reject) => {
      const ws = new WebSocket(chatWebSocketUrl(chatId));
      wsRef.current = ws;

      const timer = setTimeout(() => {
        ws.close();
        preferSseRef.current = true;
        resolve();
      }, CONNECT_TIMEOUT_MS);

      ws.onopen = () => {
        clearTimeout(timer);
        ws.send(
          JSON.stringify({
            token,
            client_timezone: getDeviceTimezone(),
          }),
        );
        resolve();
      };

      ws.onerror = () => {
        clearTimeout(timer);
        preferSseRef.current = true;
        setStreaming(false);
        setFinalizing(false);
        streamingRef.current = false;
        resolve();
      };

      ws.onclose = () => {
        clearTimeout(timer);
        if (wsRef.current === ws) {
          wsRef.current = null;
        }
        if (streamingRef.current || finalizingRef.current) {
          setStreaming(false);
          setFinalizing(false);
          streamingRef.current = false;
          finalizingRef.current = false;
          const hadContent = assistantBuffer.current.trim().length > 0;
          const draft = streamingDraftRef.current;
          const failedRegenerateBackup = regenerateBackupRef.current;
          regenerateBackupRef.current = null;
          assistantBuffer.current = "";
          reasoningBuffer.current = "";
          updateStreamingDraft(null);
          setMessages((prev) => {
            const streamingMsg = prev.find((m) => m.id === "streaming");
            if (!streamingMsg) return prev;
            if (!hadContent) {
              const withoutStreaming = prev.filter((m) => m.id !== "streaming");
              if (failedRegenerateBackup) {
                return restoreAssistantMessage(withoutStreaming, failedRegenerateBackup);
              }
              return withoutStreaming;
            }
            return prev.map((m) =>
              m.id === "streaming"
                ? {
                    ...m,
                    id: `streamed-${Date.now()}`,
                    content: draft?.content ?? m.content,
                    search_sources: draft?.search_sources ?? m.search_sources,
                  }
                : m,
            );
          });
          if (!hadContent && !failedRegenerateBackup) {
            reportError("Connection lost before the reply arrived. Try again.");
          }
        }
      };

      ws.onmessage = (event) => {
        const payload = parseChatWsPayload(String(event.data));
        if (!payload) return;
        handleChatPayload(payload);
      };
    });

    connectingRef.current = connectPromise;
    connectPromise.then(
      () => {
        connectingRef.current = null;
      },
      () => {
        connectingRef.current = null;
      },
    );
    return connectPromise;
  }, [
    token,
    chatId,
    appendStreamingPlaceholder,
    clearStreamingBubble,
    restoreRegenerateBackup,
    reportError,
    handleChatPayload,
    updateStreamingDraft,
  ]);

  const sendViaSse = useCallback(
    async (
      content: string,
      options?: {
        attachmentIds?: string[];
        model?: string | null;
        clientGeo?: ClientGeo | null;
      },
    ) => {
      if (!token || !chatId) return;
      try {
        await streamChatMessageSse({
          token,
          chatId,
          content,
          attachmentIds: options?.attachmentIds,
          model: options?.model,
          clientGeo: options?.clientGeo,
          onEvent: handleChatPayload,
        });
      } catch {
        setSendingMessageId(null);
        setStreaming(false);
        setFinalizing(false);
        streamingRef.current = false;
        clearStreamingBubble();
        reportError("Couldn't reach the server. Check your connection and try again.");
      }
    },
    [token, chatId, handleChatPayload, clearStreamingBubble, reportError],
  );

  const regenerateViaSse = useCallback(
    async (model?: string | null, clientGeo?: ClientGeo | null) => {
      if (!token || !chatId) return;
      try {
        await streamChatRegenerateSse({
          token,
          chatId,
          model,
          clientGeo,
          onEvent: handleChatPayload,
        });
      } catch {
        restoreRegenerateBackup();
        reportError("Couldn't reach the server. Check your connection and try again.");
      }
    },
    [token, chatId, handleChatPayload, restoreRegenerateBackup, reportError],
  );

  const ensureConnected = useCallback(async () => {
    try {
      await connect();
    } catch {
      reportError(
        "Could not connect to the server. Check your network and API URL.",
      );
    }
  }, [connect, reportError]);

  const sendMessage = useCallback(
    async (
      content: string,
      options?: {
        skipUserBubble?: boolean;
        trackSendingMessageId?: string;
        attachmentIds?: string[];
        localImageUri?: string | null;
        localFileUri?: string | null;
        localFileName?: string | null;
        localFileContentType?: string | null;
        model?: string | null;
        clientGeo?: ClientGeo | null;
      },
    ) => {
      if (!token || !chatId) return;

      let trackedId = options?.trackSendingMessageId ?? null;
      if (!options?.skipUserBubble) {
        trackedId = `local-${Date.now()}`;
        setMessages((prev) => [
          ...prev,
          {
            id: trackedId!,
            role: "user",
            content,
            model: null,
            local_image_uri: options?.localImageUri ?? null,
            local_file_uri: options?.localFileUri ?? null,
            local_file_name: options?.localFileName ?? null,
            local_file_content_type: options?.localFileContentType ?? null,
            created_at: new Date().toISOString(),
          },
        ]);
      }
      if (trackedId) {
        setSendingMessageId(trackedId);
      }

      await ensureConnected();
      if (preferSseRef.current || wsRef.current?.readyState !== WebSocket.OPEN) {
        await sendViaSse(content, {
          attachmentIds: options?.attachmentIds,
          model: options?.model,
          clientGeo: options?.clientGeo,
        });
        return;
      }

      assistantBuffer.current = "";
      reasoningBuffer.current = "";
      if (isVocabQuizAnswer(content) && !streamingRef.current) {
        setStreaming(true);
        streamingRef.current = true;
        updateStreamingDraft({ content: "" });
        appendStreamingPlaceholder();
      }
      wsRef.current.send(
        JSON.stringify({
          type: "message",
          content,
          attachment_ids: options?.attachmentIds ?? [],
          model: options?.model ?? null,
          ...clientGeoWsFields(options?.clientGeo),
        }),
      );
    },
    [token, chatId, ensureConnected, appendStreamingPlaceholder, updateStreamingDraft, sendViaSse],
  );

  const regenerateResponse = useCallback(
    async (model?: string | null, clientGeo?: ClientGeo | null) => {
      if (!token || !chatId) return;

      let backup: Message | null = null;
      setMessages((prev) => {
        const popped = popLastAssistantMessage(prev);
        backup = popped.backup;
        return popped.messages;
      });
      regenerateBackupRef.current = backup;

      setStreaming(true);
      streamingRef.current = true;
      assistantBuffer.current = "";
      reasoningBuffer.current = "";
      updateStreamingDraft({ content: "" });
      appendStreamingPlaceholder();

      await ensureConnected();
      if (preferSseRef.current || wsRef.current?.readyState !== WebSocket.OPEN) {
        await regenerateViaSse(model, clientGeo);
        return;
      }

      wsRef.current.send(
        JSON.stringify({
          type: "regenerate",
          model: model ?? null,
          ...clientGeoWsFields(clientGeo),
        }),
      );
    },
    [
      token,
      chatId,
      ensureConnected,
      appendStreamingPlaceholder,
      regenerateViaSse,
      updateStreamingDraft,
    ],
  );

  const editMessage = useCallback(
    async (
      messageId: string,
      content: string,
      model?: string | null,
      clientGeo?: ClientGeo | null,
    ) => {
      if (!token || !chatId || !content.trim()) return;

      let snapshot: Message[] = [];
      const localId = `local-edit-${Date.now()}`;
      setMessages((prev) => {
        snapshot = prev;
        const index = prev.findIndex((m) => m.id === messageId);
        if (index < 0) return prev;
        return [
          ...prev.slice(0, index),
          {
            id: localId,
            role: "user" as const,
            content: content.trim(),
            model: null,
            created_at: new Date().toISOString(),
          },
        ];
      });
      setSendingMessageId(localId);

      const rollbackEdit = () => {
        setSendingMessageId(null);
        setMessages(snapshot);
      };

      await ensureConnected();
      if (preferSseRef.current || wsRef.current?.readyState !== WebSocket.OPEN) {
        try {
          await streamChatEditSse({
            token,
            chatId,
            messageId,
            content: content.trim(),
            model,
            clientGeo,
            onEvent: handleChatPayload,
          });
        } catch {
          rollbackEdit();
          reportError("Couldn't reach the server. Check your connection and try again.");
        }
        return;
      }

      assistantBuffer.current = "";
      reasoningBuffer.current = "";
      wsRef.current.send(
        JSON.stringify({
          type: "edit",
          message_id: messageId,
          content: content.trim(),
          model: model ?? null,
          ...clientGeoWsFields(clientGeo),
        }),
      );
    },
    [token, chatId, ensureConnected, handleChatPayload, reportError],
  );

  const stopGeneration = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: "cancel" }));
    setStreaming(false);
    setFinalizing(false);
    streamingRef.current = false;
    const draft = streamingDraftRef.current;
    assistantBuffer.current = "";
    reasoningBuffer.current = "";
    updateStreamingDraft(null);
    setMessages((prev) => {
      const streamingMsg = prev.find((m) => m.id === "streaming");
      if (!streamingMsg) return prev;
      const content = draft?.content ?? streamingMsg.content;
      if (!content.trim()) {
        return prev.filter((m) => m.id !== "streaming");
      }
      return prev.map((m) =>
        m.id === "streaming"
          ? {
              ...m,
              id: `streamed-${Date.now()}`,
              content,
              search_sources: draft?.search_sources ?? m.search_sources,
            }
          : m,
      );
    });
  }, [updateStreamingDraft]);

  return {
    messages,
    setMessages,
    streaming,
    finalizing,
    sendingMessageId,
    sendMessage,
    regenerateResponse,
    editMessage,
    stopGeneration,
    connect,
  };
}
