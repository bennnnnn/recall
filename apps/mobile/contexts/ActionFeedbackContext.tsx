import {
  useCallback,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";
import { StyleSheet, View } from "react-native";

import { ActionBanner } from "@/components/ActionBanner";
import {
  ActionFeedbackContext,
  type ActionFeedbackApi,
  type ActionFeedbackOptions,
  type ActionFeedbackTone,
} from "@/contexts/actionFeedbackCore";
import { notifySuccess, notifyWarning } from "@/lib/haptics";
import { type IoniconName } from "@/lib/icons";

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

export function ActionFeedbackProvider({ children }: PropsWithChildren) {
  const nextId = useRef(0);
  const [item, setItem] = useState<FeedbackItem | null>(null);

  const dismiss = useCallback(() => setItem(null), []);
  const show = useCallback((message: string, options: ActionFeedbackOptions = {}) => {
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
      <View style={styles.host}>
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
      </View>
    </ActionFeedbackContext.Provider>
  );
}

const styles = StyleSheet.create({
  host: { flex: 1 },
});

export {
  useActionFeedback,
  useActionFeedbackOptional,
} from "@/contexts/actionFeedbackCore";
