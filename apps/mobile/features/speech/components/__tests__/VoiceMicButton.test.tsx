import { StyleSheet } from "react-native";
import { render } from "@testing-library/react-native";

import { COMPOSER_CONTROL_SIZE } from "@/features/chat/model/composerLogic";
import { VoiceMicButton } from "@/features/speech/components/VoiceMicButton";
import { lightTheme } from "@/lib/theme";

describe("VoiceMicButton", () => {
  it("draws the stop mark in the accent on the accent's tint", async () => {
    const { getByTestId } = await render(
      <VoiceMicButton size={36} recording transcribing={false} onPress={jest.fn()} />,
    );

    expect(getByTestId("voice-stop-mark").props.rx).toBe("5");
    expect(StyleSheet.flatten(getByTestId("voice-mic-surface").props.style)).toMatchObject({
      backgroundColor: lightTheme.primaryLight,
      borderRadius: COMPOSER_CONTROL_SIZE / 2,
    });
  });
});
