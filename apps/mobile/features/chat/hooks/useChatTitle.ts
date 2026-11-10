import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { onAppEvent } from "@/lib/appEvents";
import { useLatestRef } from "@/lib/latestRef";
import { reportFailure } from "@/lib/sentry";
import { useViewOwner } from "@/features/chat/hooks/useViewOwner";
import type { FirstReply } from "@/features/chat/model/chatTurnCore";
import { getCachedChat, noteChatTitleMissing, peekCreatedChat } from "@/features/chat/model/chatListCache";
import { firstReplyTitlePlan } from "@/features/chat/model/titleRefresh";
import {
  getChatMutationRevision,
  insertChatGlobal,
  isChatTitleGenerating,
  patchChatGlobal,
  setChatTitleGenerating,
  subscribeChatChanges,
} from "@/features/chat/drawer/drawer";

type Options = {
  token: string | null;
  chatId: string | null;
  setChatTitle: (title: string | null) => void;
  getFirstUserText?: () => string | undefined;
};
/** One chat's title on its way: `end` stops the wait, with the title or without one. */
type TitleWait = { end: (title: string | null) => void; task: Promise<void> };
/** The server waits 8 s for the topic job (title_event.TITLE_WAIT_SECONDS) before it says none came. */
const STREAM_TITLE_WAIT_MS = 12_000;

/** What one wait for a chat's title reads and sets, bound to the view that started it. */
type WaitContext = {
  waits: Map<string, TitleWait>;
  ownerSession: number;
  isCurrent: () => boolean;
  ownsHeader: () => boolean;
  setChatTitle: (title: string | null) => void;
  setTitleGenerating: (generating: boolean) => void;
};

/**
 * Waits for chat `cid`'s title: from the turn's stream when `onStream` (its title frame, or the
 * frame saying the server's wait ran out), then, with none there, from one read that waits.
 * A rename or a delete ends the wait (the drawer says both as it makes them, and the stream's
 * title arrives the same way); a title that still did not come is read with the chat list.
 */
function waitForTitle(tid: string, cid: string, onStream: boolean, ctx: WaitContext): Promise<void> {
  const { waits, ownerSession, isCurrent, ownsHeader } = ctx;
  let end: (title: string | null) => void = () => {};
  let timer: ReturnType<typeof setTimeout> | undefined;
  let settled = false;
  const stopListening = subscribeChatChanges((id, patch) => {
    if (id !== cid || (patch !== null && !patch.title?.trim())) return;
    settled = true;
    end(null);
  });
  const stopHearing = onAppEvent("chatTitleArrived", ({ chatId, title }) => { if (chatId === cid) end(title); });
  /** One step of the wait: the stream's frame (or its deadline), or one read the server holds. */
  const arrival = (fromStream: boolean) => new Promise<string | null>((resolve) => {
    end = resolve;
    if (fromStream) {
      timer = setTimeout(() => resolve(null), STREAM_TITLE_WAIT_MS);
      return;
    }
    api.getChat(tid, cid, { waitForTitle: true }).then((chat) => resolve(chat.title ?? null), (error: unknown) => {
      reportFailure("chat_title", error);
      resolve(null);
    });
  });
  const wait: TitleWait = { end: (title) => end(title), task: Promise.resolve() };
  waits.set(cid, wait);
  setChatTitleGenerating(cid);
  if (ownsHeader()) ctx.setTitleGenerating(true);
  wait.task = (async () => {
    try {
      let title = await arrival(onStream);
      // None came on the stream (the topic job ran past the server's wait, or the socket went).
      if (onStream && !title?.trim() && !settled && isCurrent()) title = await arrival(false);
      if (!isCurrent() || settled) return;
      if (title?.trim()) {
        patchChatGlobal(cid, { title });
        if (ownsHeader()) ctx.setChatTitle(title);
      } else {
        noteChatTitleMissing(cid);
      }
    } finally {
      clearTimeout(timer);
      stopListening();
      stopHearing();
      if (ownsHeader()) ctx.setTitleGenerating(false);
      if (ownerSession === getSessionGeneration() && isChatTitleGenerating(cid)) setChatTitleGenerating(null);
      if (waits.get(cid) === wait) waits.delete(cid);
    }
  })();
  return wait.task;
}

/**
 * A new chat's title after its first reply. The topic job writes it a second or two after the
 * reply; the turn's own stream brings it after `done` (a `title` frame the turn effects put in
 * the drawer, `onStream`), and a turn with no stream (a picture, live talk, a chat left first)
 * asks for it once, with a read that waits for it. It used to be polled every two seconds.
 */
export function useChatTitle({ token, chatId, setChatTitle, getFirstUserText }: Options) {
  const [titleGenerating, setTitleGenerating] = useState(false);
  const session = getSessionGeneration();
  // The header shows one chat's title; a wait from another view leaves it alone.
  const { currentView } = useViewOwner(`${chatId}:${session}`);
  const headerChatId = useLatestRef(chatId);
  const mounted = useRef(true);
  const waits = useRef(new Map<string, TitleWait>());
  useEffect(() => {
    mounted.current = true;
    const active = waits.current;
    return () => {
      mounted.current = false;
      for (const wait of active.values()) wait.end(null);
      active.clear();
    };
  }, [session]);

  /** Waits for chat `cid`'s title (`waitForTitle`); one wait per chat. */
  const awaitTitle = useCallback((tid: string, cid: string, onStream = false): Promise<void> => {
    if (!mounted.current || session !== getSessionGeneration()) return Promise.resolve();
    const existing = waits.current.get(cid);
    if (existing) return existing.task;
    const ownerSession = session;
    const owner = currentView();
    const isCurrent = () => mounted.current && ownerSession === getSessionGeneration();
    return waitForTitle(tid, cid, onStream, {
      waits: waits.current, ownerSession, isCurrent, setChatTitle, setTitleGenerating,
      ownsHeader: () => isCurrent() && owner === currentView() && cid === headerChatId.current,
    });
  }, [session, setChatTitle, currentView, headerChatId]);

  const handleFirstReply = useCallback(async (explicitChatId?: string | null, reply?: FirstReply) => {
    const cid = explicitChatId ?? chatId;
    if (!token || !cid || !mounted.current || session !== getSessionGeneration()) return;
    const ownerSession = session;
    const owner = currentView();
    const revision = getChatMutationRevision(cid);
    const isCurrent = () => mounted.current && ownerSession === getSessionGeneration() &&
      revision === getChatMutationRevision(cid);
    const ownsHeader = () => mounted.current && ownerSession === getSessionGeneration() &&
      owner === currentView() && cid === headerChatId.current;
    const plan = firstReplyTitlePlan(peekCreatedChat(cid), getCachedChat(cid), getFirstUserText?.());
    let shouldWait = plan.poll;
    if (plan.insert) {
      insertChatGlobal(plan.insert);
      if (plan.insert.title && ownsHeader()) setChatTitle(plan.insert.title);
    } else if (plan.fetch) {
      // A title that lands while the row is read (the turn's frame, a rename) is the chat's
      // title, not the row's empty one; a delete keeps the row out.
      let landed: string | undefined;
      let deleted = false;
      const stop = subscribeChatChanges((id, patch) => {
        if (id !== cid) return;
        if (patch === null) deleted = true;
        else if (patch.title?.trim()) landed = patch.title;
      });
      try {
        const read = await api.getChat(token, cid);
        if (deleted || (!landed && !isCurrent()) || !mounted.current || ownerSession !== getSessionGeneration()) return;
        const chat = landed ? { ...read, title: landed } : read;
        insertChatGlobal(chat);
        if (chat.title?.trim()) {
          if (ownsHeader()) setChatTitle(chat.title);
          shouldWait = false;
        }
      } catch (error) {
        if (!isCurrent()) return;
        // The drawer's row is best-effort: the list read brings it.
        reportFailure("chat_title", error);
      } finally {
        stop();
      }
    }
    if (shouldWait) await awaitTitle(token, cid, reply?.titleOnStream ?? false);
  }, [token, session, chatId, awaitTitle, setChatTitle, getFirstUserText, currentView, headerChatId]);

  useEffect(() => {
    setTitleGenerating(false);
    if (!chatId) setChatTitleGenerating(null);
  }, [chatId, session]);

  return { titleGenerating, awaitTitle, handleFirstReply };
}
