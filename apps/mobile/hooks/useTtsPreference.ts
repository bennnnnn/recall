import { useCallback, useEffect, useState } from "react";

import {
  getTtsModel,
  setTtsModel,
  TTS_QUALITY_MODEL,
  type TtsModelAlias,
} from "@/lib/ttsPreference";

export function useTtsPreference() {
  const [ttsModel, setLocal] = useState<TtsModelAlias>(TTS_QUALITY_MODEL);

  useEffect(() => {
    let cancelled = false;
    void getTtsModel().then((value) => {
      if (!cancelled) setLocal(value);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const selectTtsModel = useCallback((next: TtsModelAlias) => {
    setLocal(next);
    void setTtsModel(next);
  }, []);

  return { ttsModel, selectTtsModel };
}
