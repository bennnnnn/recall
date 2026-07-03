import { useEffect, useMemo, useRef } from "react";
import { StyleSheet, View } from "react-native";
import Animated, {
  Easing,
  type SharedValue,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from "react-native-reanimated";
import { useTranslation } from "react-i18next";

import { Theme, useTheme } from "@/lib/theme";

const BAR_COUNT = 36;
const MIN_H = 3;
const MAX_H = 26;

type BarProps = {
  index: number;
  meter: SharedValue<number>;
  phase: SharedValue<number>;
  stopPulse: SharedValue<number>;
  processing: SharedValue<number>;
  color: string;
};

function WaveBar({ index, meter, phase, stopPulse, processing, color }: BarProps) {
  const style = useAnimatedStyle(() => {
    const center = (BAR_COUNT - 1) / 2;
    const dist = Math.abs(index - center) / center;
    const centerWeight = 1 - dist * 0.5;
    const wave = Math.sin(phase.value * Math.PI * 2 + index * 0.38) * 0.5 + 0.5;
    const proc = processing.value;
    const recordingLevel = 0.08 + meter.value * centerWeight * (0.25 + 0.75 * wave);
    const processingLevel = 0.15 + 0.45 * centerWeight * (0.4 + 0.6 * wave);
    const level = recordingLevel * (1 - proc) + processingLevel * proc;
    const stopShrink = 1 - stopPulse.value * 0.85 * (0.4 + dist * 0.6);
    const h = MIN_H + (MAX_H - MIN_H) * level * stopShrink;
    return {
      height: h,
      opacity: 0.35 + 0.65 * level,
    };
  });

  return <Animated.View style={[styles.bar, { backgroundColor: color }, style]} />;
}

type Props = {
  recording: boolean;
  transcribing: boolean;
  meterLevel: number;
};

/** ChatGPT-style waveform in the composer while dictating or transcribing. */
export function VoiceComposerWaveform({ recording, transcribing, meterLevel }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const meter = useSharedValue(0.12);
  const phase = useSharedValue(0);
  const stopPulse = useSharedValue(0);
  const processing = useSharedValue(transcribing ? 1 : 0);
  const prevRecording = useRef(recording);

  useEffect(() => {
    meter.value = withTiming(meterLevel, { duration: 70 });
  }, [meterLevel, meter]);

  useEffect(() => {
    phase.value = withRepeat(
      withTiming(1, { duration: 1400, easing: Easing.linear }),
      -1,
      false,
    );
  }, [phase]);

  useEffect(() => {
    processing.value = withTiming(transcribing ? 1 : 0, { duration: 320 });
  }, [transcribing, processing]);

  useEffect(() => {
    if (prevRecording.current && !recording) {
      stopPulse.value = 0;
      stopPulse.value = withSequence(
        withTiming(1, { duration: 160, easing: Easing.out(Easing.cubic) }),
        withTiming(0, { duration: 280, easing: Easing.inOut(Easing.cubic) }),
      );
    }
    prevRecording.current = recording;
  }, [recording, stopPulse]);

  const indices = useMemo(() => Array.from({ length: BAR_COUNT }, (_, i) => i), []);
  const label = transcribing ? t("chat.voice_transcribing") : t("chat.voice_listening");

  return (
    <View
      style={s.wrap}
      accessibilityLabel={label}
      accessibilityLiveRegion="polite"
    >
      <View style={s.bars}>
        {indices.map((i) => (
          <WaveBar
            key={i}
            index={i}
            meter={meter}
            phase={phase}
            stopPulse={stopPulse}
            processing={processing}
            color={theme.primary}
          />
        ))}
      </View>
    </View>
  );
}

function makeStyles(_t: Theme) {
  return StyleSheet.create({
    wrap: {
      flex: 1,
      minHeight: 28,
      justifyContent: "center",
      paddingVertical: 2,
    },
    bars: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 2,
      height: MAX_H,
    },
  });
}

const styles = StyleSheet.create({
  bar: {
    width: 2.5,
    borderRadius: 2,
  },
});
