/* eslint-disable react-hooks/immutability -- Reanimated shared values are mutable by design */
import { useCallback, useEffect, useRef, useState } from "react";
import { AppState } from "react-native";
import { cancelAnimation, runOnJS, useSharedValue, withTiming } from "react-native-reanimated";

import { playbackStart, remainingPlaybackDuration } from "@/lib/animationPlayback";
import { Motion } from "@/lib/motion";

/** One native clock per scene, reset on replacement and suspended off screen. */
export function useSimulationPlayback(
  sceneKey: string,
  animated: boolean,
  reduceMotion: boolean,
  durationMs: number,
) {
  const progress = useSharedValue(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const generation = useRef(0);
  const playing = useRef(false);
  const resumeOnForeground = useRef(false);
  const appActive = useRef(AppState.currentState !== "background" && AppState.currentState !== "inactive");

  const markStopped = useCallback((run: number) => {
    if (generation.current !== run) return;
    playing.current = false;
    setIsPlaying(false);
  }, []);
  const pause = useCallback(() => {
    generation.current += 1;
    cancelAnimation(progress);
    playing.current = false;
    setIsPlaying(false);
  }, [progress]);
  const play = useCallback(() => {
    if (!animated || reduceMotion || !appActive.current) return;
    const run = ++generation.current;
    cancelAnimation(progress);
    const start = playbackStart(progress.value);
    progress.value = start;
    playing.current = true;
    setIsPlaying(true);
    progress.value = withTiming(1, {
      duration: remainingPlaybackDuration(durationMs, start),
      easing: Motion.easing.linear,
    }, (finished) => {
      if (finished) runOnJS(markStopped)(run);
    });
  }, [animated, durationMs, markStopped, progress, reduceMotion]);

  useEffect(() => {
    pause();
    progress.value = 0;
    resumeOnForeground.current = !appActive.current && animated && !reduceMotion;
    play();
    return () => {
      generation.current += 1;
      cancelAnimation(progress);
    };
  }, [animated, pause, play, progress, reduceMotion, sceneKey]);

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) => {
      appActive.current = state === "active";
      if (!appActive.current) {
        // Repeated inactive/background events must not erase the resume flag.
        resumeOnForeground.current ||= playing.current;
        pause();
      } else if (resumeOnForeground.current) {
        resumeOnForeground.current = false;
        play();
      }
    });
    return () => subscription.remove();
  }, [pause, play]);

  return { progress, isPlaying, play, pause };
}
