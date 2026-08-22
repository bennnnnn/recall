import { useCallback, useEffect, useRef, useState } from "react";
import { Alert } from "react-native";

import { transcribeSpeech } from "@/lib/api";
import {
  isVoiceInputAvailable,
  loadExpoAudio,
  requestVoicePermission,
  startVoiceRecording,
  type RecordingResult,
  type VoiceRecorder,
} from "@/lib/voiceAudio";

/** Minimum recording duration in ms — shorter taps are likely accidental. */
const MIN_RECORDING_DURATION_MS = 500;
/** Minimum fraction of metering samples that must reach speech level. */
const MIN_SPEECH_RATIO = 0.08;
/** Minimum absolute speech-level samples (~180ms at the 60ms tick) — guards
 *  against a single transient spike passing the ratio check on a short clip. */
const MIN_SPEECH_SAMPLES = 3;

type Options = {
  token: string | null;
  onTranscript: (text: string) => void;
  t: (key: string) => string;
};

export function useVoiceInput({ token, onTranscript, t }: Options) {
  const recordingRef = useRef<VoiceRecorder | null>(null);
  const meterUnsubRef = useRef<(() => void) | null>(null);
  const recordingStartedAtRef = useRef<number>(0);
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

  const stopRecording = useCallback(async (): Promise<RecordingResult | null> => {
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
      recordingStartedAtRef.current = Date.now();
      meterUnsubRef.current?.();
      meterUnsubRef.current = next.subscribeMetering((level) => setMeterLevel(level));
      setRecording(true);
    } catch {
      Alert.alert(t("common.error"), t("chat.voice_start_failed"));
    }
  }, [token, recording, transcribing, t, showUnavailable]);

  const finishRecording = useCallback(async () => {
    if (!token) return;
    setTranscribing(true);
    const result = await stopRecording();
    if (!result) {
      setTranscribing(false);
      Alert.alert(t("common.error"), t("chat.voice_recording_empty"));
      return;
    }
    // Skip transcription if the recording was too short or contained no real
    // speech. Whisper hallucinates words ("you", "thank you very much",
    // "I'm full! Please look forward to the next.") from silence/ambient noise,
    // and we can't enumerate every variant — so gate on speech *presence*
    // (sustained speech-level energy), not just a single peak that a noise
    // spike can satisfy.
    const durationMs = Date.now() - recordingStartedAtRef.current;
    const hasSpeech =
      durationMs >= MIN_RECORDING_DURATION_MS &&
      result.speechSamples >= MIN_SPEECH_SAMPLES &&
      result.speechRatio >= MIN_SPEECH_RATIO;
    if (!hasSpeech) {
      setTranscribing(false);
      Alert.alert(t("common.error"), t("chat.voice_recording_empty"));
      return;
    }
    try {
      const text = await transcribeSpeech(token, result.uri);
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
  };
}
