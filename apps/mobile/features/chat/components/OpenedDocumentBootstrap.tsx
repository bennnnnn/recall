import { useEffect, useRef, useState } from "react";
import { useGlobalSearchParams, usePathname, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { useActionFeedbackOptional } from "@/contexts/ActionFeedbackContext";
import { useAuthOptional } from "@/contexts/AuthContext";
import { useNetwork } from "@/contexts/NetworkContext";
import { watchAndroidOpenedDocuments } from "@/features/attachments/model/androidOpenedDocuments";
import { openedFileErrorMessage } from "@/features/attachments/model/attachmentErrors";
import { claimOpenedDocument, subscribeOpenedDocument } from "@/features/attachments/model/openedDocument";
import { queueComposerAttachment } from "@/features/attachments/model/pendingComposerAttachment";
import { closeDrawer, startNewChatGlobal } from "@/features/chat/drawer/drawer";
import { COMPOSER_NEW_THREAD_KEY } from "@/features/chat/model/composerThreadDraft";
import { useLatestRef } from "@/lib/latestRef";

type Router = ReturnType<typeof useRouter>;
type Place = { pathname: string; chatId: string | undefined };

/** The sign-in flow, which ends on New chat by itself: the file waits for it there. */
const SIGN_IN_ROUTES: ReadonlySet<string> = new Set(["/login", "/onboarding", "/consent"]);

/**
 * Brings New chat to the front, its composer holding the file. On a chat it starts New chat
 * (the drawer's New chat); from any other screen it goes back to the chat first; during
 * sign-in it moves nothing. True when it left a screen for the chat, whose open chat may
 * still have to give way to New chat once it shows.
 */
function showNewChat(router: Router, { pathname, chatId }: Place): boolean {
  if (SIGN_IN_ROUTES.has(pathname)) return false;
  closeDrawer();
  if (pathname === "/") {
    if (chatId) startNewChatGlobal();
    return false;
  }
  try {
    router.dismissTo("/");
    return true;
  } catch (error) {
    // No navigator yet: the file waits in New chat's composer.
    console.warn("[openedFile]", { stage: "show_chat", error: error instanceof Error ? error.name : typeof error });
    return false;
  }
}

/**
 * A file another app opened in Recall (iOS: Open in or the share sheet; Android: Open with
 * or Share) goes into New chat's composer, as a Library pick does
 * (pendingComposerAttachment.ts), and New chat comes to the front. It is taken only while
 * signed in: one that came while signed out waits through sign-in, and openedDocument.ts
 * keeps each account's file from another. A file Recall cannot attach says why.
 */
export function OpenedDocumentBootstrap() {
  const { t } = useTranslation();
  const router = useRouter();
  const pathname = usePathname();
  const { chatId } = useGlobalSearchParams<{ chatId?: string }>();
  const auth = useAuthOptional();
  const { isOffline } = useNetwork();
  const feedback = useActionFeedbackOptional();
  const signedIn = Boolean(auth?.token);
  const signInConfirmed = Boolean(auth?.profileValidated) || isOffline;
  const [arrivals, setArrivals] = useState(0);
  const place = useLatestRef<Place>({ pathname, chatId });
  /** The screen left for the chat; the next route the router shows settles it. */
  const leftRef = useRef<string | null>(null);

  useEffect(() => watchAndroidOpenedDocuments(), []);
  useEffect(() => subscribeOpenedDocument(() => setArrivals((count) => count + 1)), []);

  useEffect(() => {
    if (!signedIn) return;
    claimOpenedDocument(signInConfirmed).then(
      (pending) => {
        if (!pending) return;
        queueComposerAttachment(pending, COMPOSER_NEW_THREAD_KEY);
        if (showNewChat(router, place.current)) leftRef.current = place.current.pathname;
      },
      (error: unknown) => feedback?.error(openedFileErrorMessage(error, t)),
    );
  }, [signedIn, signInConfirmed, arrivals, router, place, feedback, t]);

  useEffect(() => {
    if (leftRef.current === null || pathname === leftRef.current) return;
    leftRef.current = null;
    if (pathname === "/" && chatId) startNewChatGlobal();
  }, [pathname, chatId]);

  return null;
}
