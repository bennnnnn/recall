import { useMemo } from "react";

import { MarkdownContent } from "@/components/MarkdownContent";
import { LinkPreviewTrust } from "@/components/markdown/LinkPreviewTrust";
import { AnswerAnchorScope, AnswerLead } from "@/components/rich/answerJump";
import { answerJumpFor } from "@/lib/markdown/answerJump";
import { formatAssistantMathExpr } from "@/lib/math/formatInput";

type Props = {
  content: string;
  streaming: boolean;
  /** The server presented `content` before saving it (isServerPresentedRow). */
  presented: boolean;
  /** The user message this reply answers: its links may show a preview. */
  userText: string | null;
  /** The reply's search sources: their links may show a preview too. */
  sources: readonly { url: string }[];
};

/**
 * An assistant reply's markdown. Only a link the user wrote or the server's
 * search returned may fetch a preview card; a link the model wrote on its own
 * stays a plain card (`lib/linkPreviewTrust.ts`). A settled reply whose answer
 * card sits under its working opens with the answer, a tap from the card
 * (`lib/markdown/answerJump.ts`), whatever the subject.
 */
export function ReplyMarkdown({ content, streaming, presented, userText, sources }: Props) {
  const jump = useMemo(() => (streaming ? null : answerJumpFor(content)), [content, streaming]);
  return (
    <LinkPreviewTrust userText={userText} sources={sources}>
      <AnswerAnchorScope>
        {jump ? <AnswerLead jump={jump} /> : null}
        <MarkdownContent
          content={content}
          streaming={streaming}
          presented={presented}
          mathFormat={formatAssistantMathExpr}
        />
      </AnswerAnchorScope>
    </LinkPreviewTrust>
  );
}
