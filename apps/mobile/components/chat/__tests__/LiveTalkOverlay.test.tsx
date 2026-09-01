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
  Motion: { duration: { soft: 200, snappy: 200 }, easing: { inOut: undefined, in: undefined } },
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
    headerInset: 96,
    composerClearance: 88,
    onToggle: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("does not pause from the orb and has no Listening/Speaking copy", async () => {
    const onToggle = jest.fn();
    const { getByTestId, queryByText } = await render(
      <LiveTalkOverlay {...base} phase="speaking" onToggle={onToggle} />,
    );

    expect(queryByText("chat.live_talk_speaking")).toBeNull();
    expect(queryByText("chat.live_talk_listening")).toBeNull();
    await fireEvent.press(getByTestId("live-talk-orb"));
    expect(onToggle).not.toHaveBeenCalled();
  });

  it("uses a listen visual while recording and a speak visual while the assistant talks", async () => {
    const listen = await render(<LiveTalkOverlay {...base} phase="recording" recording />);
    expect(listen.getByTestId("live-talk-orb-listen")).toBeTruthy();
    const speak = await render(<LiveTalkOverlay {...base} phase="speaking" />);
    expect(speak.getByTestId("live-talk-orb-speak")).toBeTruthy();
  });

  it("starts below the chat header and above the composer", async () => {
    const { getByTestId } = await render(<LiveTalkOverlay {...base} phase="idle" />);
    expect(getByTestId("live-talk-overlay")).toHaveStyle({ top: 96, bottom: 88 });
  });
});
