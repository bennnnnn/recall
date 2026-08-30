import { fireEvent, render } from "@testing-library/react-native";

import { LiveTalkOverlay } from "@/components/chat/LiveTalkOverlay";

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

jest.mock("@/lib/motion", () => ({
  useReduceMotion: () => true,
  Motion: { duration: { soft: 200 }, easing: { inOut: undefined } },
}));

jest.mock("expo-linear-gradient", () => {
  const { View } = jest.requireActual("react-native") as typeof import("react-native");
  return { LinearGradient: View };
});

describe("LiveTalkOverlay", () => {
  const base = {
    visible: true,
    meterLevel: 0.2,
    recording: false,
    onClose: jest.fn(),
    onToggle: jest.fn(),
    onInterrupt: jest.fn(),
  };

  it("pauses from the orb and takes the floor from Speak", async () => {
    const onToggle = jest.fn();
    const onInterrupt = jest.fn();
    const { getByLabelText, getByText } = await render(
      <LiveTalkOverlay {...base} phase="speaking" onToggle={onToggle} onInterrupt={onInterrupt} />,
    );

    expect(getByText("chat.live_talk_speaking")).toBeTruthy();
    await fireEvent.press(getByLabelText("chat.live_talk_pause_a11y"));
    expect(onToggle).toHaveBeenCalled();
    await fireEvent.press(getByLabelText("chat.live_talk_interrupt_a11y"));
    expect(onInterrupt).toHaveBeenCalled();
  });
});
