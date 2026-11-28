import { fireEvent, render } from "@testing-library/react-native";

import { ComposerSendControls } from "@/features/chat/components/ComposerSendControls";
import { makeChatComposerStyles } from "@/features/chat/components/chatComposerStyles";
import { startSendUpload } from "@/features/chat/model/sendUpload";
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

it("turns Send into Cancel while the send's file uploads", async () => {
  const upload = startSendUpload();
  try {
    const screen = await render(
      <ComposerSendControls
        s={makeChatComposerStyles(lightTheme)}
        streaming={false}
        onStop={jest.fn()}
        onSend={jest.fn()}
        showSend
        sendBusy
        isOffline={false}
        attachBusy={false}
        showMic={false}
        voiceRecording={false}
        voiceTranscribing={false}
      />,
    );
    fireEvent.press(screen.getByLabelText("chat.cancel_upload"));
    expect(upload.signal.aborted).toBe(true);
  } finally {
    upload.finish();
  }
});

it("sends while messages are left", async () => {
  const { screen, onSend } = renderSend(false);
  fireEvent.press((await screen).getByLabelText("chat.send_a11y"));
  expect(onSend).toHaveBeenCalledTimes(1);
});
