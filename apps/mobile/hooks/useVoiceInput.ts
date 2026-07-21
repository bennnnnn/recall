import { useCallback, useEffect, useRef, useState } from "react";
import { Alert } from "react-native";

import { transcribeSpeech } from "@/lib/api";
import {
  isVoiceInputAvailable,
  loadExpoAudio,
  requestVoicePermission,
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
  const meterUnsubRef = useRef<(() => void) | null>(null);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [meterLevel, setMeterLevel] = useState(0.12);
  const [voiceInputAvailable, setVoiceInputAvailable] = useState(false);

  useEffect(() => {
    setVoiceInputAvailable(isVoiceInputAvailable());
  }, []);

  const showUnavailable = useCallback(() => {
    Alert.alert(t("chat.voice_unavailable_title"), t("chat.voice_unavailable_body"));
  }, [t]);

  const stopRecording = useCallback(async (): Promise<string | null> => {
    const active = recordingRef.current;
    recordingRef.current = null;
    meterUnsubRef.current?.();
    meterUnsubRef.current = null;
    setRecording(false);
    setMeterLevel(0.12);
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
      const mod = loadExpoAudio();
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
      meterUnsubRef.current?.();
      meterUnsubRef.current = next.subscribeMetering((level) => setMeterLevel(level));
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
    setTranscribing(true);
    const uri = await stopRecording();
    if (!uri) {
      setTranscribing(false);
      Alert.alert(t("common.error"), t("chat.voice_recording_empty"));
      return;
    }
    try {
      const text = await transcribeSpeech(token, uri);
      onTranscript(text);
    } catch (error) {
      const message = error instanceof Error ? error.message : "";
      if (/network request failed|failed to fetch|timeout/i.test(message)) {
        Alert.alert(t("common.error"), t("chat.voice_network_failed"));
      } else if (message.includes("recording_empty")) {
        Alert.alert(t("common.error"), t("chat.voice_recording_empty"));
      } else if (message.includes("transcribe_empty")) {
        Alert.alert(t("common.error"), t("chat.voice_transcribe_empty"));
      } else {
        Alert.alert(t("common.error"), t("chat.voice_transcribe_failed"));
      }
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

  useEffect(() => {
    return () => {
      meterUnsubRef.current?.();
      meterUnsubRef.current = null;
      const active = recordingRef.current;
      recordingRef.current = null;
      if (active) {
        void active.stop().catch(() => undefined);
      }
    };
  }, []);

  return {
    voiceInputAvailable,
    voiceRecording: recording,
    voiceTranscribing: transcribing,
    voiceMeterLevel: meterLevel,
    toggleVoiceInput: toggleRecording,
    cancelVoiceInput: cancelRecording,
    voiceInputRebuildHint: VOICE_INPUT_REBUILD_HINT,
  };
}
