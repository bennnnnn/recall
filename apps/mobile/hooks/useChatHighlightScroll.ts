import { useCallback, useEffect, useRef, useState } from "react";
import type { FlashListRef } from "@shopify/flash-list";
import { useRouter } from "expo-router";

import type { Message } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { registerChatHighlightClearer } from "@/lib/drawer";

type Router = ReturnType<typeof useRouter>;
type ViewOwner = { session: number; chatId: string | null };
type HighlightRequest = { owner: ViewOwner; id: string; cursor?: string; loading?: boolean };
type Options = {
  routeChatId?: string;
  routeHighlightMessage: string | undefined;
  router: Router;
  messages: Message[];
  hasMoreOlder: boolean;
  chatLoading?: boolean;
  loadingOlder: boolean;
  token: string | null;
  chatId: string | null;
  loadOlderMessages: () => Promise<void>;
  listRef: React.RefObject<FlashListRef<Message> | null>;
};
const HIGHLIGHT_MS = 3500;

/** Page toward a selected search hit, then scroll/highlight within its conversation. */
export function useChatHighlightScroll({
  routeChatId, routeHighlightMessage, router, messages, hasMoreOlder, chatLoading = false, loadingOlder,
  token, chatId, loadOlderMessages, listRef,
}: Options) {
  const session = getSessionGeneration();
  const destination = routeChatId ?? chatId;
  const ownerRef = useRef<ViewOwner>({ session, chatId: destination });
  if (ownerRef.current.session !== session || ownerRef.current.chatId !== destination) {
    ownerRef.current = { session, chatId: destination };
  }
  const owner = ownerRef.current;
  const latest = useRef({ messages, chatId, token });
  latest.current = { messages, chatId, token };
  const mounted = useRef(true);
  const pending = useRef<HighlightRequest | null>(null);
  const [highlight, setHighlight] = useState<HighlightRequest | null>(null);
  const [pageRevision, setPageRevision] = useState(0);
  const frame = useRef<number | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelScheduled = useCallback(() => {
    if (frame.current != null) cancelAnimationFrame(frame.current);
    if (timer.current != null) clearTimeout(timer.current);
    frame.current = null;
    timer.current = null;
  }, []);
  const current = useCallback(() => mounted.current && ownerRef.current === owner &&
    session === getSessionGeneration() && Boolean(latest.current.token), [owner, session]);

  const clearHighlight = useCallback(() => {
    pending.current = null;
    cancelScheduled();
    setHighlight(null);
  }, [cancelScheduled]);
  useEffect(() => {
    registerChatHighlightClearer(clearHighlight);
    return () => registerChatHighlightClearer(null);
  }, [clearHighlight]);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; pending.current = null; cancelScheduled(); };
  }, [cancelScheduled]);
  useEffect(() => {
    clearHighlight();
  }, [owner, clearHighlight]);
  useEffect(() => {
    if (!routeHighlightMessage || !owner.chatId || !current()) return;
    cancelScheduled();
    const request = { owner, id: routeHighlightMessage };
    pending.current = request;
    setHighlight(request);
    router.setParams({ highlightMessage: undefined });
  }, [routeHighlightMessage, owner, current, router, cancelScheduled]);

  useEffect(() => {
    const request = pending.current;
    if (!request || request.owner !== owner || !current() || chatId !== owner.chatId || messages.length === 0) return;
    const index = messages.findIndex((message) => message.id === request.id);
    if (index >= 0) {
      if (frame.current != null) return;
      frame.current = requestAnimationFrame(() => {
        frame.current = null;
        if (!current() || pending.current !== request || latest.current.chatId !== owner.chatId) return;
        // Another page may have prepended rows since this frame was scheduled.
        const latestIndex = latest.current.messages.findIndex((message) => message.id === request.id);
        if (latestIndex < 0) return;
        listRef.current?.scrollToIndex({ index: latestIndex, animated: true, viewPosition: 0.5 });
        pending.current = null;
        timer.current = setTimeout(() => {
          timer.current = null;
          if (current()) setHighlight((value) => value === request ? null : value);
        }, HIGHLIGHT_MS);
      });
      return;
    }
    const cursor = messages[0].id;
    if (!hasMoreOlder || chatLoading || loadingOlder || request.loading || request.cursor === cursor) return;
    request.cursor = cursor;
    request.loading = true;
    void (async () => {
      try { await loadOlderMessages(); }
      catch { /* The history loader reports failures; Load earlier remains available for retry. */ }
      finally {
        request.loading = false;
        if (current() && pending.current === request) setPageRevision((value) => value + 1);
      }
    })();
  }, [owner, current, chatId, messages, hasMoreOlder, chatLoading, loadingOlder, loadOlderMessages, listRef, pageRevision]);

  return { highlightedMessageId: highlight?.owner === owner && token ? highlight.id : null };
}
