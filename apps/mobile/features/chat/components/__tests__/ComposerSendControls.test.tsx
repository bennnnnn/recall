import { fireEvent, render } from "@testing-library/react-native";

import { ComposerSendControls } from "@/features/chat/components/ComposerSendControls";
import { makeChatComposerStyles } from "@/features/chat/components/chatComposerStyles";
import { lightTheme } from "@/lib/theme";

function renderSend(quotaBlocked: boolean) {
  const onSend = jest.fn();
  const screen = render(
    <ComposerSendControls
      s={makeChatComposerStyles(lightTheme)}
      streaming={false}
      onStop={jest.fn()}
      onSend={onSend}
      showSend
      sendBusy={false}
      isOffline={false}
      quotaBlocked={quotaBlocked}
      attachBusy={false}
      showMic={false}
      voiceRecording={false}
      voiceTranscribing={false}
    />,
  );
  return { screen, onSend };
}

it("greys Send out while a free plan's messages are used up, and says why", async () => {
  const { screen, onSend } = renderSend(true);
  const button = (await screen).getByLabelText("chat.send_a11y");
  expect(button.props.accessibilityState.disabled).toBe(true);
  expect(button.props.accessibilityHint).toBe("chat.quota_exceeded_free");
  fireEvent.press(button);
  expect(onSend).not.toHaveBeenCalled();
});

it("sends while messages are left", async () => {
  const { screen, onSend } = renderSend(false);
  fireEvent.press((await screen).getByLabelText("chat.send_a11y"));
  expect(onSend).toHaveBeenCalledTimes(1);
});
