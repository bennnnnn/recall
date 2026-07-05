import { useCallback, useEffect, useMemo, useState } from "react";

import type { ModelInfo } from "@/lib/api";
import {
  buildModelOptions,
  resolveSelectedModelLabel,
} from "@/lib/chatComposerLogic";
import { MODEL_CATALOG_FALLBACK } from "@/lib/modelCatalogFallback";

type Options = {
  autoEnabled: boolean;
  modelEnabledSet: Set<string>;
  models?: ModelInfo[];
  isPro: boolean;
  labelFor: (id: string) => string | undefined;
  autoModelId: string;
  t: (key: string) => string;
  closeAttachSheetRef: React.MutableRefObject<() => void>;
};

export function useChatComposerState({
  autoEnabled,
  modelEnabledSet,
  models: modelsProp,
  isPro,
  labelFor,
  autoModelId,
  t,
  closeAttachSheetRef,
}: Options) {
  const models = modelsProp ?? MODEL_CATALOG_FALLBACK;
  const [showModelPicker, setShowModelPicker] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string>(autoModelId);

  const autoLabel = t("settings.model_auto");

  const modelOptions = useMemo(
    () =>
      buildModelOptions({
        autoEnabled,
        autoModelId,
        autoLabel,
        modelEnabledSet,
        models,
        isPro,
        t,
      }),
    [autoEnabled, modelEnabledSet, models, isPro, autoModelId, autoLabel, t],
  );

  useEffect(() => {
    if (modelOptions.length === 0) return;
    if (!modelOptions.some((option) => option.id === selectedModel)) {
      setSelectedModel(modelOptions[0].id);
    }
  }, [modelOptions, selectedModel]);

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
    setShowModelPicker(false);
    closeAttachSheet();
  }, [closeAttachSheet]);

  const toggleModelPicker = useCallback(() => {
    closeAttachSheet();
    setShowModelPicker((v) => !v);
  }, [closeAttachSheet]);

  const selectModel = useCallback((id: string) => {
    if (!modelOptions.some((option) => option.id === id)) return;
    setSelectedModel(id);
    setShowModelPicker(false);
  }, [modelOptions]);

  return {
    showModelPicker,
    selectedModel,
    modelOptions,
    selectedModelLabel,
    closePickers,
    toggleModelPicker,
    selectModel,
  };
}
