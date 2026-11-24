import { useCallback } from "react";
import { useTranslation } from "react-i18next";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { PASTE_MAX_PAGES } from "@/features/attachments/model/pastedText";
import { readComposerChange, readPastedText, type ComposerPaste } from "@/features/chat/model/composerPaste";
import { messageTooLong } from "@/features/chat/model/messageLimit";
import { useLatestRef } from "@/lib/latestRef";
import type { ActionFeedbackTone } from "@/ui/feedback/ActionBanner";
import type { IconName } from "@/ui/icons/names";

type Options = {
  input: string;
  /**
   * Makes a long paste the composer's attachment; false when it could not, and the paste
   * then stays text. Absent, or while the composer holds an attachment already (a message
   * takes one), a long paste stays text in the field. One longer than a paste may be is
   * refused either way.
   */
  onPasteAsFile?: (text: string) => boolean;
  /** Where a refusal is said; the app's toast when absent. */
  onNotice?: (message: string, icon?: IconName, tone?: ActionFeedbackTone) => void;
  hasAttachment: boolean;
  /**
   * The field's own handling (useMathKeyboardInsert): `onChangeText` for every edit that is
   * not a long paste, `pasteText` to put text in at the caret (the maths pad's Paste key).
   */
  field: { onChangeText: (next: string) => void; pasteText: (text: string) => unknown };
};

/**
 * Long text in the composer. More than PASTE_ATTACH_MIN_CHARS pasted in one change go in as a
 * "Pasted text" attachment, and more than a paste may hold add nothing and say why
 * (features/chat/model/composerPaste.ts); everything else reaches the field unchanged.
 * `tooLong`: the draft is longer than a message may be (features/chat/model/messageLimit.ts),
 * so the composer says so and Send waits.
 */
export function useComposerPaste({ input, onPasteAsFile, onNotice, hasAttachment, field }: Options) {
  const { onChangeText, pasteText: insertText } = field;
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const inputRef = useLatestRef(input);
  const pasteAsFileRef = useLatestRef(hasAttachment ? undefined : onPasteAsFile);

  /** True when `paste` was handled here; the field then holds what it should. */
  const take = useCallback(
    (paste: ComposerPaste): boolean => {
      if (paste.kind === "text") return false;
      if (paste.kind === "too_long") {
        const message = t("chat.paste_too_long", { pages: PASTE_MAX_PAGES });
        if (onNotice) onNotice(message, "alert-circle", "error");
        else feedback?.error(message);
        return true;
      }
      if (!pasteAsFileRef.current?.(paste.text)) return false;
      // Left as it was, the field reverts to the draft by itself (a controlled TextInput).
      if (paste.remaining !== inputRef.current) onChangeText(paste.remaining);
      return true;
    },
    [pasteAsFileRef, feedback, inputRef, onChangeText, onNotice, t],
  );

  /** The field's onChangeText: a long paste is taken out of it. */
  const onFieldChange = useCallback(
    (next: string) => {
      if (!take(readComposerChange(inputRef.current, next))) onChangeText(next);
    },
    [inputRef, onChangeText, take],
  );

  /** The maths pad's Paste key. */
  const onPadPaste = useCallback(
    (text: string) => {
      if (!take(readPastedText(text, inputRef.current))) insertText(text);
    },
    [inputRef, insertText, take],
  );

  return { onFieldChange, onPadPaste, tooLong: messageTooLong(input) };
}
