import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, BackHandler } from "react-native";

import { useDrawer } from "@/contexts/DrawerContext";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { api } from "@/lib/api";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import {
  LIVE_TALK_ECHO_GUARD_MS,
  liveTalkCanTakeFloor,
  liveTalkErrorGate,
  liveTalkGate,
  liveTalkOrbAction,
  liveTalkSilenceDecision,
  type LiveTalkGate,
  type LiveTalkPhase,
  type LiveTalkStatus,
} from "@/lib/liveTalkLogic";
import { pauseSpeaking, playSpeechAudio, resumeSpeaking, stopSpeaking } from "@/lib/pronunciation";
import { isVoiceInputAvailable, readRecordingBase64, speechUploadFromUri } from "@/lib/voiceAudio";

type Options = {
  token: string | null;
  isOffline: boolean;
  onUpgrade: () => void;
  t: (key: string) => string;
};

export function useLiveTalk({ token, isOffline, onUpgrade, t }: Options) {
  const feedback = useActionFeedbackOptional();
  const drawerOpen = useDrawer().isOpen;
  const [visible, setVisible] = useState(false);
  const [phase, setPhase] = useState<LiveTalkPhase>("idle");
  const [status, setStatus] = useState<LiveTalkStatus | null>(null);
  const phaseRef = useRef(phase);
  const visibleRef = useRef(false);
  const sessionGen = useRef(0);
  const heardSpeechRef = useRef(false);
  const silenceStartedAtRef = useRef<number | null>(null);
  const recordingStartedAtRef = useRef(0);
  const endingUtteranceRef = useRef(false);
  const autoListenRef = useRef(false);
  const emptyStreakRef = useRef(0);

  phaseRef.current = phase;
  visibleRef.current = visible;

  const alertForGate = useCallback(
    (gate: LiveTalkGate, opts?: { overModal?: boolean }) => {
      if (gate === "upgrade") {
        onUpgrade();
        return;
      }
      const overModal = opts?.overModal === true;
      const message =
        gate === "limit"
          ? t("chat.live_talk_limit_body")
          : gate === "offline"
            ? t("chat.offline_body")
            : t("chat.live_talk_unavailable_body");
      if (overModal) {
        const title =
          gate === "limit"
            ? t("chat.live_talk_limit_title")
            : gate === "offline"
              ? t("common.error")
              : t("chat.live_talk_unavailable_title");
        Alert.alert(title, message);
        return;
      }
      reportRecoverableError(feedback, message);
    },
    [feedback, onUpgrade, t],
  );

  const voice = useVoiceInput({
    token,
    t,
    recordingFormat: "wav",
    onTranscript: () => undefined,
    onTranscribeError: () => undefined,
  });

  const startRecordingRef = useRef(voice.startRecording);
  const cancelRecordingRef = useRef(voice.cancelRecording);
  startRecordingRef.current = voice.startRecording;
  cancelRecordingRef.current = voice.cancelRecording;

  const beginListen = useCallback(async () => {
    if (!token || isOffline || !visibleRef.current) return;
    if (phaseRef.current === "recording" || phaseRef.current === "thinking") return;
    heardSpeechRef.current = false;
    silenceStartedAtRef.current = null;
    recordingStartedAtRef.current = Date.now();
    const started = await startRecordingRef.current();
    if (!started) return;
    if (!visibleRef.current) {
      void cancelRecordingRef.current();
      return;
    }
    setPhase("recording");
  }, [token, isOffline]);

  const finishListen = useCallback(async () => {
    if (!token || endingUtteranceRef.current) return;
    endingUtteranceRef.current = true;
    const gen = sessionGen.current;
    setPhase("thinking");
    const uri = await cancelRecordingRef.current();
    if (sessionGen.current !== gen) {
      endingUtteranceRef.current = false;
      return;
    }
    if (!uri) {
      endingUtteranceRef.current = false;
      emptyStreakRef.current += 1;
      autoListenRef.current = emptyStreakRef.current < 3;
      setPhase("idle");
      return;
    }
    const audioBase64 = await readRecordingBase64(uri);
    if (sessionGen.current !== gen) {
      endingUtteranceRef.current = false;
      return;
    }
    if (!audioBase64) {
      endingUtteranceRef.current = false;
      emptyStreakRef.current += 1;
      autoListenRef.current = emptyStreakRef.current < 3;
      setPhase("idle");
      return;
    }
    emptyStreakRef.current = 0;
    try {
      const spoken = await api.liveTalkSpeak(token, audioBase64, speechUploadFromUri(uri).name);
      if (sessionGen.current !== gen) {
        endingUtteranceRef.current = false;
        return;
      }
      setStatus({
        enabled: true,
        entitled: true,
        remaining: spoken.remaining,
        limit: spoken.limit,
      });
      setPhase("speaking");
      const played = await playSpeechAudio(spoken.audio_base64, spoken.content_type);
      if (sessionGen.current !== gen) {
        endingUtteranceRef.current = false;
        return;
      }
      if (!played.ok) {
        Alert.alert(t("chat.read_aloud_unavailable_title"), t("chat.read_aloud_unavailable_body"));
      } else {
        await new Promise((resolve) => setTimeout(resolve, LIVE_TALK_ECHO_GUARD_MS));
        if (sessionGen.current !== gen) {
          endingUtteranceRef.current = false;
          return;
        }
      }
      autoListenRef.current = true;
      setPhase("idle");
    } catch (error) {
      if (sessionGen.current !== gen) {
        endingUtteranceRef.current = false;
        return;
      }
      alertForGate(liveTalkErrorGate(error), { overModal: true });
      setPhase("idle");
    } finally {
      endingUtteranceRef.current = false;
    }
  }, [token, alertForGate, t]);

  const close = useCallback(() => {
    sessionGen.current += 1;
    stopSpeaking();
    endingUtteranceRef.current = false;
    autoListenRef.current = false;
    void cancelRecordingRef.current();
    setPhase("idle");
    setVisible(false);
  }, []);

  const open = useCallback(async () => {
    if (!token) return;
    if (!isVoiceInputAvailable() || !voice.voiceInputAvailable) {
      reportRecoverableError(feedback, t("chat.live_talk_unavailable_body"));
      return;
    }
    try {
      const next = await api.liveTalkStatus(token);
      setStatus(next);
      const gate = liveTalkGate(next, isOffline);
      if (gate !== "ok") {
        alertForGate(gate);
        return;
      }
      sessionGen.current += 1;
      emptyStreakRef.current = 0;
      autoListenRef.current = true;
      setPhase("idle");
      setVisible(true);
    } catch (error) {
      alertForGate(liveTalkErrorGate(error));
    }
  }, [token, isOffline, voice.voiceInputAvailable, t, alertForGate, feedback]);

  const toggle = useCallback(async () => {
    const action = liveTalkOrbAction(phase);
    if (action === "none") return;
    if (action === "cancelThink") {
      sessionGen.current += 1;
      endingUtteranceRef.current = false;
      autoListenRef.current = true;
      setPhase("idle");
      return;
    }
    if (action === "finishListen") {
      await finishListen();
      return;
    }
    await beginListen();
  }, [phase, finishListen, beginListen]);

  const togglePlayback = useCallback(() => {
    if (phaseRef.current === "speaking") {
      if (!pauseSpeaking()) {
        sessionGen.current += 1;
        stopSpeaking();
        autoListenRef.current = true;
        setPhase("idle");
        return;
      }
      setPhase("paused");
      return;
    }
    if (phaseRef.current === "paused") {
      if (!resumeSpeaking()) {
        sessionGen.current += 1;
        stopSpeaking();
        autoListenRef.current = true;
        setPhase("idle");
        return;
      }
      setPhase("speaking");
    }
  }, []);

  const interrupt = useCallback(() => {
    if (!liveTalkCanTakeFloor(phase)) return;
    sessionGen.current += 1;
    stopSpeaking();
    autoListenRef.current = true;
    void cancelRecordingRef.current();
    setPhase("idle");
  }, [phase]);

  const yieldToComposer = useCallback(() => {
    if (!visibleRef.current) return;
    sessionGen.current += 1;
    stopSpeaking();
    endingUtteranceRef.current = false;
    autoListenRef.current = false;
    void cancelRecordingRef.current();
    setPhase("idle");
  }, []);

  useEffect(() => {
    if (!visible || phase !== "idle" || !autoListenRef.current) return;
    autoListenRef.current = false;
    void beginListen();
  }, [visible, phase, beginListen]);

  useEffect(() => {
    if (phase !== "recording") return;
    const next = liveTalkSilenceDecision({
      meter: voice.voiceMeterLevel,
      now: Date.now(),
      recordingStartedAt: recordingStartedAtRef.current,
      heardSpeech: heardSpeechRef.current,
      silenceStartedAt: silenceStartedAtRef.current,
    });
    heardSpeechRef.current = next.heardSpeech;
    silenceStartedAtRef.current = next.silenceStartedAt;
    if (next.shouldStop) void finishListen();
  }, [phase, voice.voiceMeterLevel, finishListen]);

  useEffect(() => {
    if (!visible) return;
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      if (drawerOpen) return false;
      close();
      return true;
    });
    return () => sub.remove();
  }, [visible, drawerOpen, close]);

  useEffect(() => {
    return () => {
      stopSpeaking();
    };
  }, []);

  return {
    visible,
    phase,
    meterLevel: voice.voiceMeterLevel,
    recording: phase === "recording",
    open,
    close,
    toggle,
    togglePlayback,
    yieldToComposer,
    interrupt,
  };
}
