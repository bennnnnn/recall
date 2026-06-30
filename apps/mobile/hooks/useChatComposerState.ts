import { useCallback, useMemo, useState } from "react";

import {
  buildModelOptions,
  resolvePlanLabel,
  resolveSelectedModelLabel,
} from "@/lib/chatComposerLogic";

type Options = {
  isPro: boolean;
  autoEnabled: boolean;
  modelEnabledSet: Set<string>;
  labelFor: (id: string) => string | undefined;
  autoModelId: string;
  t: (key: string) => string;
  closeAttachSheetRef: React.MutableRefObject<() => void>;
  onRequestUpgrade: () => void;
};

export function useChatComposerState({
  isPro,
  autoEnabled,
  modelEnabledSet,
  labelFor,
  autoModelId,
  t,
  closeAttachSheetRef,
  onRequestUpgrade,
}: Options) {
  const [showPlanPicker, setShowPlanPicker] = useState(false);
  const [showModelPicker, setShowModelPicker] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string>(autoModelId);

  const autoLabel = t("settings.model_auto");
  const planLabel = resolvePlanLabel(isPro, t("chat.plan_pro"), t("chat.plan_free"));

  const modelOptions = useMemo(
    () =>
      buildModelOptions({
        autoEnabled,
        autoModelId,
        autoLabel,
        modelEnabledSet,
        labelFor,
      }),
    [autoEnabled, modelEnabledSet, labelFor, autoModelId, autoLabel],
  );

  const selectedModelLabel = resolveSelectedModelLabel(
    selectedModel,
    autoModelId,
    autoLabel,
    labelFor,
  );

  const closeAttachSheet = useCallback(() => {
    closeAttachSheetRef.current();
  }, [closeAttachSheetRef]);

  const closePickers = useCallback(() => {
    setShowPlanPicker(false);
    setShowModelPicker(false);
    closeAttachSheet();
  }, [closeAttachSheet]);

  const togglePlanPicker = useCallback(() => {
    closeAttachSheet();
    setShowModelPicker(false);
    setShowPlanPicker((v) => !v);
  }, [closeAttachSheet]);

  const toggleModelPicker = useCallback(() => {
    closeAttachSheet();
    setShowPlanPicker(false);
    setShowModelPicker((v) => !v);
  }, [closeAttachSheet]);

  const selectPlan = useCallback(
    (plan: "free" | "pro") => {
      setShowPlanPicker(false);
      if (plan === "pro" && !isPro) {
        onRequestUpgrade();
      }
    },
    [isPro, onRequestUpgrade],
  );

  const selectModel = useCallback((id: string) => {
    setSelectedModel(id);
    setShowModelPicker(false);
  }, []);

  return {
    showPlanPicker,
    showModelPicker,
    selectedModel,
    planLabel,
    modelOptions,
    selectedModelLabel,
    closePickers,
    togglePlanPicker,
    toggleModelPicker,
    selectPlan,
    selectModel,
  };
}
