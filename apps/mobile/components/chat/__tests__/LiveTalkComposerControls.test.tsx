import { fireEvent, render } from "@testing-library/react-native";

import { LiveTalkComposerControls } from "@/components/chat/LiveTalkComposerControls";

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

describe("LiveTalkComposerControls", () => {
  it("puts the speaker next to close and pauses from the speaker", async () => {
    const onSpeakerPress = jest.fn();
    const onClose = jest.fn();
    const { getByLabelText, getByTestId } = await render(
      <LiveTalkComposerControls phase="speaking" onSpeakerPress={onSpeakerPress} onClose={onClose} />,
    );

    await fireEvent.press(getByLabelText("chat.live_talk_pause_a11y"));
    expect(onSpeakerPress).toHaveBeenCalled();
    await fireEvent.press(getByTestId("live-talk-close"));
    expect(onClose).toHaveBeenCalled();
  });
});
