import { useCallback, useMemo, useState } from "react";

import {
  buildModelOptions,
  resolveSelectedModelLabel,
} from "@/lib/chatComposerLogic";

type Options = {
  autoEnabled: boolean;
  modelEnabledSet: Set<string>;
  labelFor: (id: string) => string | undefined;
  autoModelId: string;
  t: (key: string) => string;
  closeAttachSheetRef: React.MutableRefObject<() => void>;
};

export function useChatComposerState({
  autoEnabled,
  modelEnabledSet,
  labelFor,
  autoModelId,
  t,
  closeAttachSheetRef,
}: Options) {
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
    setShowModelPicker(false);
    closeAttachSheet();
  }, [closeAttachSheet]);

  const toggleModelPicker = useCallback(() => {
    closeAttachSheet();
    setShowModelPicker((v) => !v);
  }, [closeAttachSheet]);

  const selectModel = useCallback((id: string) => {
    setSelectedModel(id);
    setShowModelPicker(false);
  }, []);

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
