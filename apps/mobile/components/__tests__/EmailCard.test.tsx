import { fireEvent, render, waitFor } from "@testing-library/react-native";

import { EmailCard } from "@/components/rich/EmailCard";
import {
  AssistantMessageScope,
  EmailDraftPersistProvider,
} from "@/contexts/emailDraftPersist";

jest.mock("expo-clipboard", () => ({ setStringAsync: jest.fn() }));
jest.mock("expo-haptics", () => ({
  impactAsync: jest.fn(),
  notificationAsync: jest.fn(),
  selectionAsync: jest.fn(),
}));
jest.mock("@expo/vector-icons", () => ({ Ionicons: "Ionicons" }));
jest.mock("react-native-svg", () => {
  const { View } = jest.requireActual("react-native") as typeof import("react-native");
  return { __esModule: true, default: View, Svg: View, Path: View };
});
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

const MESSAGE_ID = "11111111-1111-1111-1111-111111111111";

describe("EmailCard persist", () => {
  it("saves the current draft when Done is pressed", async () => {
    const save = jest.fn().mockResolvedValue(true);
    const { getByLabelText, getByPlaceholderText } = await render(
      <EmailDraftPersistProvider save={save}>
        <AssistantMessageScope messageId={MESSAGE_ID}>
          <EmailCard
            draft={{ to: "a@b.com", subject: "Hi", body: "Hello" }}
          />
        </AssistantMessageScope>
      </EmailDraftPersistProvider>,
    );

    await fireEvent.press(getByLabelText("chat.email_card_edit"));
    await fireEvent.changeText(getByPlaceholderText("chat.email_card_subject_placeholder"), "Shorter");
    await fireEvent.press(getByLabelText("chat.email_card_done"));

    await waitFor(() => {
      expect(save).toHaveBeenCalledWith(MESSAGE_ID, {
        to: "a@b.com",
        subject: "Shorter",
        body: "Hello",
      });
    });
  });

  it("does not persist a streaming placeholder id", async () => {
    const save = jest.fn().mockResolvedValue(true);
    const { getByLabelText, getByPlaceholderText } = await render(
      <EmailDraftPersistProvider save={save}>
        <AssistantMessageScope messageId="streaming">
          <EmailCard
            draft={{ to: "a@b.com", subject: "Hi", body: "Hello" }}
          />
        </AssistantMessageScope>
      </EmailDraftPersistProvider>,
    );

    await fireEvent.press(getByLabelText("chat.email_card_edit"));
    await fireEvent.changeText(getByPlaceholderText("chat.email_card_subject_placeholder"), "Shorter");
    await fireEvent.press(getByLabelText("chat.email_card_done"));

    await waitFor(() => {
      expect(getByLabelText("chat.email_card_edit")).toBeTruthy();
    });
    expect(save).not.toHaveBeenCalled();
  });
});
