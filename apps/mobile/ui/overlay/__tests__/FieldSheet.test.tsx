import { act, fireEvent, render } from "@testing-library/react-native";
import { useState } from "react";
import { Pressable, Text } from "react-native";

import { FieldSheet } from "../FieldSheet";

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 34, left: 0, right: 0 }),
}));
jest.mock("@/lib/reduceMotion", () => ({ useReduceMotion: () => false }));
let mockAnswer: (discard: boolean) => void = () => undefined;
const mockConfirm = jest.fn(
  (_options: unknown) => new Promise<boolean>((resolve) => { mockAnswer = resolve; }),
);
jest.mock("@/ui/overlay/dialogs", () => ({
  confirmDialog: (options: unknown) => mockConfirm(options),
}));

/** A screen that opens the sheet on a saved value, as Settings does. */
function Screen({ saved, onClose }: { saved: string; onClose: () => void }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  return (
    <>
      <Pressable testID="open" onPress={() => { setText(saved); setOpen(true); }} />
      <FieldSheet
        visible={open}
        title="Custom instructions"
        value={text}
        onChangeText={setText}
        onClose={() => { onClose(); setOpen(false); }}
        onSave={() => setOpen(false)}
      />
      <Text testID="open-state">{open ? "open" : "closed"}</Text>
    </>
  );
}

beforeEach(() => jest.clearAllMocks());

// A tap on the scrim or Back threw away typed custom instructions without a word.
it("asks before closing with changed text, and stays open to keep editing", async () => {
  const onClose = jest.fn();
  const view = await render(<Screen saved="Be brief." onClose={onClose} />);
  await fireEvent.press(view.getByTestId("open"));
  await fireEvent.changeText(view.getByDisplayValue("Be brief."), "Be brief. Use metric units.");

  await fireEvent.press(view.getByTestId("app-sheet-backdrop"));
  expect(mockConfirm).toHaveBeenCalledWith(expect.objectContaining({
    title: "common.discard_changes_title",
    confirmLabel: "common.discard",
    cancelLabel: "common.keep_editing",
    destructive: true,
  }));
  await act(async () => mockAnswer(false));
  expect(onClose).not.toHaveBeenCalled();
  expect(view.getByTestId("open-state").props.children).toBe("open");

  await fireEvent.press(view.getByText("common.cancel"));
  await act(async () => mockAnswer(true));
  expect(onClose).toHaveBeenCalledTimes(1);
});

it("closes at once when the text is as it opened", async () => {
  const onClose = jest.fn();
  const view = await render(<Screen saved="Be brief." onClose={onClose} />);
  await fireEvent.press(view.getByTestId("open"));
  // Typed and put back: nothing to lose.
  await fireEvent.changeText(view.getByDisplayValue("Be brief."), "Be brief. ");
  await fireEvent.press(view.getByTestId("app-sheet-backdrop"));
  expect(mockConfirm).not.toHaveBeenCalled();
  expect(onClose).toHaveBeenCalledTimes(1);
});
