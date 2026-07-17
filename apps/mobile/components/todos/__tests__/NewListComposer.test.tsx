import { fireEvent, render } from "@testing-library/react-native";

import { NewListComposer } from "@/components/todos/NewListComposer";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

describe("NewListComposer", () => {
  it("saves a trimmed name and ignores empty submit", async () => {
    const onSave = jest.fn();
    const onCancel = jest.fn();
    const { getByLabelText, getByText } = await render(
      <NewListComposer onCancel={onCancel} onSave={onSave} />,
    );

    const input = getByLabelText("lists.group_name_label");
    await fireEvent.changeText(input, "  Groceries  ");
    await fireEvent.press(getByText("common.add"));
    expect(onSave).toHaveBeenCalledWith("Groceries");

    onSave.mockClear();
    await fireEvent.changeText(input, "   ");
    await fireEvent.press(getByText("common.add"));
    expect(onSave).not.toHaveBeenCalled();
  });
});
