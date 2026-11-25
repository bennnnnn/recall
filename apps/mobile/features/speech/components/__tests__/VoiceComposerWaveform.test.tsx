import type { SharedValue } from "react-native-reanimated";
import { StyleSheet } from "react-native";
import { render } from "@testing-library/react-native";

import { VoiceComposerWaveform } from "@/features/speech/components/VoiceComposerWaveform";
import { hideLiveDictation, showLiveDictation } from "@/features/speech/model/liveDictationView";
import { lightTheme } from "@/lib/theme";

jest.mock("react-native-reanimated", () => {
  const { View } = jest.requireActual("react-native");
  const linear = (t: number) => t;
  return {
    __esModule: true,
    default: { View },
    Easing: {
      linear,
      ease: linear,
      sin: linear,
      inOut: () => linear,
      out: () => linear,
      in: () => linear,
      cubic: linear,
    },
    useSharedValue: (init: number) => ({ value: init }),
    useAnimatedStyle: (fn: () => object) => fn(),
    useAnimatedReaction: () => undefined,
    withTiming: (v: number) => v,
    withRepeat: (v: number) => v,
  };
});

describe("VoiceComposerWaveform", () => {
  it("shows Transcribing… instead of a live listening wave", async () => {
    const { getByText, queryByText } = await render(
      <VoiceComposerWaveform recording={false} transcribing meterLevel={{ value: 0.2 } as SharedValue<number>} />,
    );
    expect(getByText("chat.voice_transcribing")).toBeOnTheScreen();
    expect(queryByText("chat.voice_listening")).toBeNull();
  });

  it("draws the bars in the accent, as the stop button beside them", async () => {
    const { getAllByTestId } = await render(
      <VoiceComposerWaveform recording meterLevel={{ value: 0.4 } as SharedValue<number>} transcribing={false} />,
    );
    const bars = getAllByTestId("voice-waveform-bar");
    expect(bars.length).toBeGreaterThan(0);
    expect(
      bars.every((node) => StyleSheet.flatten(node.props.style).backgroundColor === lightTheme.primary),
    ).toBe(true);
  });

  it("keeps a live take's words up while its last ones land, and says it is transcribing", async () => {
    showLiveDictation({ phase: "finishing", text: "see you at noon" });
    const { getByTestId, getByLabelText, getAllByTestId } = await render(
      <VoiceComposerWaveform recording={false} transcribing meterLevel={{ value: 0.2 } as SharedValue<number>} />,
    );
    expect(getByTestId("voice-live-words")).toHaveTextContent("see you at noon");
    // A screen reader heard "Listening" on a row marked busy.
    expect(getByLabelText("chat.voice_transcribing")).toBeOnTheScreen();
    expect(getAllByTestId("voice-waveform-bar")).toHaveLength(12);
    hideLiveDictation();
  });
});
