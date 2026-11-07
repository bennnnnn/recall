import type { ReactNode, RefObject } from "react";
import type { FlashListRef } from "@shopify/flash-list";

import { ScrollToViewProvider } from "@/components/rich/answerJump";
import { ClarifyActionsProvider } from "@/components/rich/clarifyContext";
import { useScrollToView } from "@/features/chat/hooks/useScrollToView";
import type { Message } from "@/lib/api";
import { EmailDraftPersistProvider } from "@/features/drafts/context/emailDraftPersist";
import type { EmailDraft } from "@/lib/richBlocks";

type Props = {
  /** Saves an edited email card on its message. */
  saveEmailDraft: (messageId: string, draft: EmailDraft) => Promise<boolean>;
  /** Sends a user message through the chat's send path (a clarify card's picks); false when refused. */
  send: (text: string) => Promise<boolean>;
  /** A reply is streaming or saving: cards that send wait. */
  busy: boolean;
  /** The thread, and the header over its top: a reply's answer line scrolls it to the card. */
  listRef: RefObject<FlashListRef<Message> | null>;
  topInset: number;
  children: ReactNode;
};

/** What the cards inside a reply reach in the chat around them. */
export function ChatReplyProviders({ saveEmailDraft, send, busy, listRef, topInset, children }: Props) {
  const scrollTo = useScrollToView(listRef, topInset);
  return (
    <EmailDraftPersistProvider save={saveEmailDraft}>
      <ClarifyActionsProvider send={send} busy={busy}>
        <ScrollToViewProvider scrollTo={scrollTo}>{children}</ScrollToViewProvider>
      </ClarifyActionsProvider>
    </EmailDraftPersistProvider>
  );
}
