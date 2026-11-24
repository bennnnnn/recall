/**
 * A long paste becomes the composer's attachment, a paste past the limit adds nothing, and a
 * draft longer than a message holds Send back with a note (features/chat/hooks/useComposerPaste.ts,
 * features/chat/model/messageLimit.ts).
 */
import { fireEvent, render } from "@testing-library/react-native";

import { ChatComposer } from "@/features/chat/components/ChatComposer";
import { PASTE_ATTACH_MIN_CHARS } from "@/features/chat/model/composerPaste";
import { MESSAGE_MAX_CHARS } from "@/features/chat/model/messageLimit";

import { DraftHarness } from "./DraftHarness";

const mockError = jest.fn();
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => ({ error: mockError }) }));
jest.mock("expo-linear-gradient", () => {
  const { View } = jest.requireActual("react-native") as typeof import("react-native");
  return { LinearGradient: View };
});
jest.mock("@/contexts/AuthContext", () => ({ useAuthToken: () => "t" }));
jest.mock("@/features/speech/components/VoiceComposerWaveform", () => ({ VoiceComposerWaveform: () => null }));
jest.mock("@/features/speech/components/VoiceMicButton", () => ({ VoiceMicButton: () => null }));
jest.mock("@/features/speech/components/LiveTalkButton", () => ({ LiveTalkButton: () => null }));
jest.mock("@/features/attachments/components/ComposerAttachmentPreview", () => ({
  ComposerAttachmentPreview: () => null,
}));

const baseProps = {
  visible: true,
  streaming: false,
  pendingAttachment: null,
  onRemoveAttachment: jest.fn(),
  onCloseAttachSheet: jest.fn(),
  onPickAttachment: jest.fn(),
  onSend: jest.fn(),
  onStop: jest.fn(),
  isOffline: false,
};

beforeEach(() => jest.clearAllMocks());

describe("pasting into the composer", () => {
  it("hands a long paste over as a file and keeps the draft in the field", async () => {
    const onPasteAsFile = jest.fn(() => true);
    const pasted = "p".repeat(PASTE_ATTACH_MIN_CHARS + 1);
    const { getByTestId } = await render(
      <DraftHarness input="Summarize: ">
        <ChatComposer {...baseProps} onPasteAsFile={onPasteAsFile} />
      </DraftHarness>,
    );
    await fireEvent.changeText(getByTestId("chat-composer-input"), `Summarize: ${pasted}`);
    expect(onPasteAsFile).toHaveBeenCalledWith(pasted);
    expect(getByTestId("chat-composer-input").props.value).toBe("Summarize: ");
  });

  it("types a short paste in as text", async () => {
    const onPasteAsFile = jest.fn(() => true);
    const pasted = "p".repeat(PASTE_ATTACH_MIN_CHARS);
    const { getByTestId } = await render(
      <DraftHarness input="">
        <ChatComposer {...baseProps} onPasteAsFile={onPasteAsFile} />
      </DraftHarness>,
    );
    await fireEvent.changeText(getByTestId("chat-composer-input"), pasted);
    expect(onPasteAsFile).not.toHaveBeenCalled();
    expect(getByTestId("chat-composer-input").props.value).toBe(pasted);
  });

  it("adds nothing from a paste past the limit and says why", async () => {
    const onPasteAsFile = jest.fn(() => true);
    const { getByTestId } = await render(
      <DraftHarness input="draft">
        <ChatComposer {...baseProps} onPasteAsFile={onPasteAsFile} />
      </DraftHarness>,
    );
    await fireEvent.changeText(getByTestId("chat-composer-input"), `draft${"x".repeat(200_001)}`);
    expect(onPasteAsFile).not.toHaveBeenCalled();
    expect(mockError).toHaveBeenCalledWith("chat.paste_too_long");
    expect(getByTestId("chat-composer-input").props.value).toBe("draft");
  });
});

describe("a draft longer than a message", () => {
  it("says so under the field and holds Send back", async () => {
    const onSend = jest.fn();
    const { getByLabelText, getByTestId } = await render(
      <DraftHarness input={"a".repeat(MESSAGE_MAX_CHARS + 1)}>
        <ChatComposer {...baseProps} onSend={onSend} />
      </DraftHarness>,
    );
    expect(getByTestId("composer-too-long").props.children).toBe("chat.message_too_long");
    const send = getByLabelText("chat.send_a11y");
    expect(send.props.accessibilityState).toMatchObject({ disabled: true });
    await fireEvent.press(send);
    expect(onSend).not.toHaveBeenCalled();
  });

  it("shows no note and sends at the limit", async () => {
    const onSend = jest.fn();
    const { getByLabelText, queryByTestId } = await render(
      <DraftHarness input={"a".repeat(MESSAGE_MAX_CHARS)}>
        <ChatComposer {...baseProps} onSend={onSend} />
      </DraftHarness>,
    );
    expect(queryByTestId("composer-too-long")).toBeNull();
    await fireEvent.press(getByLabelText("chat.send_a11y"));
    expect(onSend).toHaveBeenCalledTimes(1);
  });
});
