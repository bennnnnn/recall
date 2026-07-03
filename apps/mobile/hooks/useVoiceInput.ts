import { useCallback, useEffect, useRef, useState } from "react";
import { Alert } from "react-native";

import { getApiUrl } from "@/lib/config";
import {
  isVoiceInputAvailable,
  startVoiceRecording,
  type VoiceRecorder,
  VOICE_INPUT_REBUILD_HINT,
} from "@/lib/voiceAudio";

type Options = {
  token: string | null;
  onTranscript: (text: string) => void;
  t: (key: string) => string;
};

export function useVoiceInput({ token, onTranscript, t }: Options) {
  const recordingRef = useRef<VoiceRecorder | null>(null);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [voiceInputAvailable, setVoiceInputAvailable] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void isVoiceInputAvailable().then((available) => {
      if (!cancelled) setVoiceInputAvailable(available);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const showUnavailable = useCallback(() => {
    Alert.alert(t("chat.voice_unavailable_title"), t("chat.voice_unavailable_body"));
  }, [t]);

  const stopRecording = useCallback(async (): Promise<string | null> => {
    const active = recordingRef.current;
    recordingRef.current = null;
    setRecording(false);
    if (!active) return null;
    try {
      return await active.stop();
    } catch {
      return null;
    }
  }, []);

  const startRecording = useCallback(async () => {
    if (!token || recording || transcribing) return;
    try {
      const { loadExpoAudio, requestVoicePermission } = await import("@/lib/voiceAudio");
      const mod = await loadExpoAudio();
      if (!mod) {
        showUnavailable();
        return;
      }
      const permission = await requestVoicePermission(mod);
      if (!permission.granted) {
        Alert.alert(t("chat.voice_permission_title"), t("chat.voice_permission_body"));
        return;
      }
      const next = await startVoiceRecording();
      if (!next) {
        showUnavailable();
        return;
      }
      recordingRef.current = next;
      setRecording(true);
    } catch {
      Alert.alert(t("common.error"), t("chat.voice_start_failed"));
    }
  }, [token, recording, transcribing, t, showUnavailable]);

  const cancelRecording = useCallback(async () => {
    await stopRecording();
  }, [stopRecording]);

  const finishRecording = useCallback(async () => {
    if (!token) return;
    const uri = await stopRecording();
    if (!uri) return;
    setTranscribing(true);
    try {
      const form = new FormData();
      form.append("file", {
        uri,
        name: "speech.m4a",
        type: "audio/m4a",
      } as unknown as Blob);
      const response = await fetch(`${getApiUrl()}/speech/transcribe`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const data = (await response.json()) as { text?: string };
      const text = (data.text ?? "").trim();
      if (text) {
        onTranscript(text);
      }
    } catch {
      Alert.alert(t("common.error"), t("chat.voice_transcribe_failed"));
    } finally {
      setTranscribing(false);
    }
  }, [token, stopRecording, onTranscript, t]);

  const toggleRecording = useCallback(async () => {
    if (transcribing) return;
    if (!voiceInputAvailable) {
      showUnavailable();
      return;
    }
    if (recording) {
      await finishRecording();
      return;
    }
    await startRecording();
  }, [
    transcribing,
    voiceInputAvailable,
    recording,
    finishRecording,
    startRecording,
    showUnavailable,
  ]);

  return {
    voiceInputAvailable,
    voiceRecording: recording,
    voiceTranscribing: transcribing,
    toggleVoiceInput: toggleRecording,
    cancelVoiceInput: cancelRecording,
    voiceInputRebuildHint: VOICE_INPUT_REBUILD_HINT,
  };
}
