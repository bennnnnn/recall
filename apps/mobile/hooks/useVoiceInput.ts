import { useCallback, useEffect, useRef, useState } from "react";
import { Alert } from "react-native";

import { transcribeSpeech } from "@/lib/api";
import {
  isVoiceInputAvailable,
  loadExpoAudio,
  requestVoicePermission,
  startVoiceRecording,
  type VoiceRecorder,
  type VoiceRecordingFormat,
} from "@/lib/voiceAudio";

type TranscribeFail = "empty" | "network" | "failed";

type Options = {
  token: string | null;
  onTranscript: (text: string) => void;
  t: (key: string) => string;
  recordingFormat?: VoiceRecordingFormat;
  /** When set, skip default alerts so the caller can refund / show live-talk copy. */
  onTranscribeError?: (reason: TranscribeFail) => void;
};

export function useVoiceInput({
  token,
  onTranscript,
  t,
  recordingFormat = "aac",
  onTranscribeError,
}: Options) {
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

  const startRecording = useCallback(async (): Promise<boolean> => {
    if (!token || recording || transcribing) return false;
    try {
      const mod = loadExpoAudio();
      if (!mod) {
        showUnavailable();
        return false;
      }
      const permission = await requestVoicePermission(mod);
      if (!permission.granted) {
        Alert.alert(t("chat.voice_permission_title"), t("chat.voice_permission_body"));
        return false;
      }
      const next = await startVoiceRecording(recordingFormat);
      if (!next) {
        showUnavailable();
        return false;
      }
      recordingRef.current = next;
      meterUnsubRef.current?.();
      meterUnsubRef.current = next.subscribeMetering((level) => setMeterLevel(level));
      setRecording(true);
      return true;
    } catch {
      Alert.alert(t("common.error"), t("chat.voice_start_failed"));
      return false;
    }
  }, [token, recording, transcribing, t, showUnavailable, recordingFormat]);

  const finishRecording = useCallback(async (): Promise<string | null> => {
    if (!token) return null;
    setTranscribing(true);
    const uri = await stopRecording();
    if (!uri) {
      setTranscribing(false);
      onTranscribeError?.("empty");
      if (!onTranscribeError) {
        Alert.alert(t("common.error"), t("chat.voice_recording_empty"));
      }
      return null;
    }
    try {
      const text = await transcribeSpeech(token, uri);
      onTranscript(text);
      return text;
    } catch (error) {
      const message = error instanceof Error ? error.message : "";
      const reason: TranscribeFail = /network request failed|failed to fetch|timeout/i.test(
        message,
      )
        ? "network"
        : message.includes("recording_empty") || message.includes("transcribe_empty")
          ? "empty"
          : "failed";
      onTranscribeError?.(reason);
      if (!onTranscribeError) {
        if (reason === "network") {
          Alert.alert(t("common.error"), t("chat.voice_network_failed"));
        } else if (message.includes("recording_empty")) {
          Alert.alert(t("common.error"), t("chat.voice_recording_empty"));
        } else if (message.includes("transcribe_empty")) {
          Alert.alert(t("common.error"), t("chat.voice_transcribe_empty"));
        } else {
          Alert.alert(t("common.error"), t("chat.voice_transcribe_failed"));
        }
      }
      return null;
    } finally {
      setTranscribing(false);
    }
  }, [token, stopRecording, onTranscript, onTranscribeError, t]);

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
    startRecording,
    finishRecording,
    cancelRecording: stopRecording,
  };
}
