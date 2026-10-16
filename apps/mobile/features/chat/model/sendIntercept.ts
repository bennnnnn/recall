import type { Message } from "@/lib/api";
import type { PendingAttachment } from "@/features/attachments/model/attachments";
import {
  extractImageGenPromptFromThread,
  extractAttachedImageEditPrompt,
  extractImageRevisionPrompt,
  imageGenRevisionContext,
} from "@/features/images/model/imageGenIntent";
import { extractImageLookupQuery } from "@/features/images/model/imageLookupIntent";
import { stemSubjectOwnsTurn } from "@/features/images/model/stemSubjectOwnsTurn";

export type ImageReference = { attachment?: PendingAttachment; ids?: string[] };

export type SendIntercept =
  /** A reference photo: the backend's image_search attaches it to an ordinary reply. */
  | { kind: "lookup" }
  | { kind: "send" }
  | { kind: "generate"; prompt: string; reference?: ImageReference }
  /** An image is still generating, so the tap is dropped. */
  | { kind: "drop" }
  /** The user left the view while the server was asked. */
  | { kind: "stale" };

type InterceptInput = {
  text: string;
  attachment: PendingAttachment | null;
  messages: Message[];
  canGenerate: boolean;
  imageGenerating: boolean;
  token: string | null;
  /** Runs just before the server is asked. */
  onServerCheck: () => void;
  isCurrentView: () => boolean;
};

/**
 * What the composer makes of a send before chat sees it: a photo lookup, an image to
 * generate, or a normal send. Synchronous unless it asks the server, so a plain send
 * claims its double-send guard in the same tick. ES-05 replaces the inside with the
 * server's verdict.
 */
export function resolveSendIntercept(input: InterceptInput): SendIntercept | Promise<SendIntercept> {
  const { text, attachment, messages } = input;
  // Reference-photo lookup ("show me an ear") wants a real photo, not AI
  // art — checked first so generation's bare colloquial fallback can't
  // misclassify "show me a picture of X" as a draw request.
  if (!attachment && extractImageLookupQuery(text)) return { kind: "lookup" };

  // Image-gen intent → /images/generate from the composer (no sheet, no LLM stub).
  // Do not gate on client isPaid — plan can be stale while the API still knows Pro;
  // submitPrompt / the API open upgrade or generate. Never let the model invent
  // "the app will attach an image shortly" without calling generate.
  if (!input.canGenerate || (attachment && attachment.kind !== "image")) return { kind: "send" };
  const revisionContext = imageGenRevisionContext(messages);
  const revision = attachment?.kind === "image"
    ? extractAttachedImageEditPrompt(text)
    : extractImageRevisionPrompt(text, revisionContext);
  const prompt = extractImageGenPromptFromThread(text, messages) ?? revision;
  if (!prompt) return { kind: "send" };
  if (input.imageGenerating) return { kind: "drop" };
  const reference = attachment ? { attachment }
    : revision && revisionContext.referenceAttachmentId
      ? { ids: [revisionContext.referenceAttachmentId] } : undefined;
  input.onServerCheck();
  return askServer(input, prompt, reference);
}

async function askServer(
  input: InterceptInput,
  prompt: string,
  reference: ImageReference | undefined,
): Promise<SendIntercept> {
  const ownedBySubject = await stemSubjectOwnsTurn(input.token, input.text);
  if (!input.isCurrentView()) return { kind: "stale" };
  // "draw ethanol" is a structure and a lens question is optics: the
  // server leaves them to their subject, so the chat send takes them.
  return ownedBySubject ? { kind: "send" } : { kind: "generate", prompt, reference };
}
