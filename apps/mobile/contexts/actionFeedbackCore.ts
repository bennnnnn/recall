import { createContext, useContext } from "react";

import { type IoniconName } from "@/lib/icons";

export type ActionFeedbackTone = "success" | "info" | "warning" | "error";

export type ActionFeedbackOptions = {
  tone?: ActionFeedbackTone;
  icon?: IoniconName;
  haptic?: boolean;
};

export type ActionFeedbackApi = {
  show: (message: string, options?: ActionFeedbackOptions) => void;
  success: (
    message: string,
    options?: Omit<ActionFeedbackOptions, "tone">,
  ) => void;
  info: (message: string, options?: Omit<ActionFeedbackOptions, "tone">) => void;
  warning: (
    message: string,
    options?: Omit<ActionFeedbackOptions, "tone">,
  ) => void;
  error: (message: string, options?: Omit<ActionFeedbackOptions, "tone">) => void;
  dismiss: () => void;
};

export const ActionFeedbackContext = createContext<ActionFeedbackApi | null>(null);

export function useActionFeedback(): ActionFeedbackApi {
  const value = useContext(ActionFeedbackContext);
  if (!value) {
    throw new Error("useActionFeedback must be used within ActionFeedbackProvider");
  }
  return value;
}

/** Useful for isolated hooks/tests that can also run outside the app root. */
export function useActionFeedbackOptional(): ActionFeedbackApi | null {
  return useContext(ActionFeedbackContext);
}
