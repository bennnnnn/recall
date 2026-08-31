import { useCallback, useEffect, useRef, useState } from "react";
import { Alert } from "react-native";

import { transcribeSpeech } from "@/lib/api";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import {
  isVoiceInputAvailable,
  loadExpoAudio,
  requestVoicePermission,
  startVoiceRecording,
  VOICE_MAX_RECORDING_MS,
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

const VOICE_SPEECH_LEVEL = 0.28;
const VOICE_MIN_SPEECH_SAMPLES = 2;

export function useVoiceInput({
  token,
  onTranscript,
  t,
  recordingFormat = "aac",
  onTranscribeError,
}: Options) {
  const feedback = useActionFeedbackOptional();
  const recordingRef = useRef<VoiceRecorder | null>(null);
  const meterUnsubRef = useRef<(() => void) | null>(null);
  const maxTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const finishRecordingRef = useRef<() => Promise<string | null>>(async () => null);
  const speechSamplesRef = useRef(0);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [meterLevel, setMeterLevel] = useState(0.12);
  const [voiceInputAvailable, setVoiceInputAvailable] = useState(false);

  useEffect(() => {
    setVoiceInputAvailable(isVoiceInputAvailable());
  }, []);

  const showUnavailable = useCallback(() => {
    reportRecoverableError(feedback, t("chat.voice_unavailable_body"));
  }, [feedback, t]);

  const stopRecording = useCallback(async (): Promise<string | null> => {
    if (maxTimerRef.current != null) {
      clearTimeout(maxTimerRef.current);
      maxTimerRef.current = null;
    }
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
      speechSamplesRef.current = 0;
      recordingRef.current = next;
      meterUnsubRef.current?.();
      meterUnsubRef.current = next.subscribeMetering((level) => {
        setMeterLevel(level);
        if (level >= VOICE_SPEECH_LEVEL) speechSamplesRef.current += 1;
      });
      setRecording(true);
      if (maxTimerRef.current != null) clearTimeout(maxTimerRef.current);
      maxTimerRef.current = setTimeout(() => {
        if (onTranscribeError) return;
        void finishRecordingRef.current();
      }, VOICE_MAX_RECORDING_MS);
      return true;
    } catch {
      reportRecoverableError(feedback, t("chat.voice_start_failed"));
      return false;
    }
  }, [token, recording, transcribing, t, showUnavailable, recordingFormat, onTranscribeError, feedback]);

  const finishRecording = useCallback(async (): Promise<string | null> => {
    if (!token) return null;
    setTranscribing(true);
    const heardSpeech = speechSamplesRef.current >= VOICE_MIN_SPEECH_SAMPLES;
    const uri = await stopRecording();
    if (!uri || !heardSpeech) {
      setTranscribing(false);
      onTranscribeError?.("empty");
      if (!onTranscribeError) {
        reportRecoverableError(feedback, t("chat.voice_recording_empty"));
      }
      return null;
    }
    try {
      const text = await transcribeSpeech(token, uri);
      onTranscript(text);
      return text;
    } catch (error) {
      const message = error instanceof Error ? error.message : "";
      const reason: TranscribeFail =
        /network request failed|failed to fetch|timeout|timed out|could not reach/i.test(
          message,
        )
        ? "network"
        : message.includes("recording_empty") || message.includes("transcribe_empty")
          ? "empty"
          : "failed";
      onTranscribeError?.(reason);
      if (!onTranscribeError) {
        if (reason === "network") {
          reportRecoverableError(feedback, t("chat.voice_network_failed"));
        } else if (message.includes("recording_empty")) {
          reportRecoverableError(feedback, t("chat.voice_recording_empty"));
        } else if (message.includes("transcribe_empty")) {
          reportRecoverableError(feedback, t("chat.voice_transcribe_empty"));
        } else {
          reportRecoverableError(feedback, t("chat.voice_transcribe_failed"));
        }
      }
      return null;
    } finally {
      setTranscribing(false);
    }
  }, [token, stopRecording, onTranscript, onTranscribeError, feedback, t]);

  finishRecordingRef.current = finishRecording;

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
      if (maxTimerRef.current != null) {
        clearTimeout(maxTimerRef.current);
        maxTimerRef.current = null;
      }
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
