import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";

import {
  ActionBanner,
  type ActionFeedbackTone,
} from "@/components/ActionBanner";
import { notifySuccess, notifyWarning } from "@/lib/haptics";
import { type IoniconName } from "@/lib/icons";

type ShowOptions = {
  tone?: ActionFeedbackTone;
  icon?: IoniconName;
  haptic?: boolean;
};

type ActionFeedbackApi = {
  show: (message: string, options?: ShowOptions) => void;
  success: (message: string, options?: Omit<ShowOptions, "tone">) => void;
  info: (message: string, options?: Omit<ShowOptions, "tone">) => void;
  warning: (message: string, options?: Omit<ShowOptions, "tone">) => void;
  error: (message: string, options?: Omit<ShowOptions, "tone">) => void;
  dismiss: () => void;
};

type FeedbackItem = {
  id: number;
  message: string;
  tone: ActionFeedbackTone;
  icon: IoniconName;
};

const DEFAULT_ICONS: Record<ActionFeedbackTone, IoniconName> = {
  success: "checkmark-circle",
  info: "information-circle",
  warning: "warning",
  error: "alert-circle",
};

const ActionFeedbackContext = createContext<ActionFeedbackApi | null>(null);

export function ActionFeedbackProvider({ children }: PropsWithChildren) {
  const nextId = useRef(0);
  const [item, setItem] = useState<FeedbackItem | null>(null);

  const dismiss = useCallback(() => setItem(null), []);
  const show = useCallback((message: string, options: ShowOptions = {}) => {
    const tone = options.tone ?? "success";
    nextId.current += 1;
    setItem({
      id: nextId.current,
      message,
      tone,
      icon: options.icon ?? DEFAULT_ICONS[tone],
    });
    if (options.haptic === false || tone === "info") return;
    if (tone === "success") notifySuccess();
    else notifyWarning();
  }, []);

  const api = useMemo<ActionFeedbackApi>(
    () => ({
      show,
      success: (message, options) => show(message, { ...options, tone: "success" }),
      info: (message, options) => show(message, { ...options, tone: "info" }),
      warning: (message, options) => show(message, { ...options, tone: "warning" }),
      error: (message, options) => show(message, { ...options, tone: "error" }),
      dismiss,
    }),
    [dismiss, show],
  );

  return (
    <ActionFeedbackContext.Provider value={api}>
      {children}
      {item ? (
        <ActionBanner
          key={item.id}
          message={item.message}
          icon={item.icon}
          tone={item.tone}
          onDismiss={dismiss}
        />
      ) : null}
    </ActionFeedbackContext.Provider>
  );
}

export function useActionFeedback(): ActionFeedbackApi {
  const value = useContext(ActionFeedbackContext);
  if (!value) {
    throw new Error("useActionFeedback must be used within ActionFeedbackProvider");
  }
  return value;
}
