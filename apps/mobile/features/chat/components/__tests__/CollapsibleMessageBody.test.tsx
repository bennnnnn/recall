import { fireEvent, render } from "@testing-library/react-native";
import { Text } from "react-native";

import { CollapsibleMessageBody } from "@/features/chat/components/CollapsibleMessageBody";

function Body({ messageKey }: { messageKey: string }) {
  return (
    <CollapsibleMessageBody messageKey={messageKey}>
      <Text>{`long message ${messageKey}`}</Text>
    </CollapsibleMessageBody>
  );
}

// The chat list reuses a row for another message and keeps its state: one long message
// opened with Show more made the next long message drawn in that row open too.
it("starts folded when its row is reused for another message", async () => {
  const view = await render(<Body messageKey="m1" />);
  await fireEvent.press(view.getByLabelText("common.show_more"));
  expect(view.getByLabelText("common.show_less")).toBeTruthy();

  await view.rerender(<Body messageKey="m2" />);
  expect(view.getByLabelText("common.show_more")).toBeTruthy();

  // Back on the message it was opened for, the row shows it open again.
  await view.rerender(<Body messageKey="m1" />);
  expect(view.getByLabelText("common.show_less")).toBeTruthy();
});

it("folds again on Show less", async () => {
  const view = await render(<Body messageKey="m1" />);
  await fireEvent.press(view.getByLabelText("common.show_more"));
  await fireEvent.press(view.getByLabelText("common.show_less"));
  expect(view.getByLabelText("common.show_more")).toBeTruthy();
});
