import { render } from "@testing-library/react-native";

import { VoiceComposerWaveform } from "@/components/chat/VoiceComposerWaveform";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

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
    withTiming: (v: number) => v,
    withRepeat: (v: number) => v,
  };
});

describe("VoiceComposerWaveform", () => {
  it("shows Transcribing… instead of a live listening wave", async () => {
    const { getByText, queryByText } = await render(
      <VoiceComposerWaveform recording={false} transcribing meterLevel={0.2} />,
    );
    expect(getByText("chat.voice_transcribing")).toBeOnTheScreen();
    expect(queryByText("chat.voice_listening")).toBeNull();
  });
});
