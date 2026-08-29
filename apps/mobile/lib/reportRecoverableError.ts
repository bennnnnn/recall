import { Alert } from "react-native";

import type { ActionFeedbackApi } from "@/contexts/actionFeedbackCore";

/** Recoverable failures: in-tree banner when the provider exists, native fallback otherwise. */
export function reportRecoverableError(
  feedback: ActionFeedbackApi | null | undefined,
  message: string,
): void {
  if (feedback) {
    feedback.error(message);
    return;
  }
  Alert.alert(message);
}

export function reportRecoverableWarning(
  feedback: ActionFeedbackApi | null | undefined,
  message: string,
): void {
  if (feedback) {
    feedback.warning(message);
    return;
  }
  Alert.alert(message);
}
