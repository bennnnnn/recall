import { fireEvent, render, screen } from "@testing-library/react-native";

import { MathConverterUnitSheet } from "@/features/chat/components/MathConverterUnitSheet";
import { UNITS_BY_CATEGORY } from "@/lib/unitConverter";

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

describe("MathConverterUnitSheet", () => {
  it("tells a screen reader which unit is picked", async () => {
    const onPickUnit = jest.fn();
    await render(
      <MathConverterUnitSheet
        visible
        category="length"
        selectedId="km"
        onClose={jest.fn()}
        onPickCategory={jest.fn()}
        onPickUnit={onPickUnit}
      />,
    );

    const units = screen.getAllByRole("radio");
    expect(units).toHaveLength(UNITS_BY_CATEGORY.length.length);
    const picked = screen.getAllByRole("radio", { checked: true });
    expect(picked).toHaveLength(1);
    expect(picked[0]).toBe(screen.getByTestId("math-converter-unit-km"));

    await fireEvent.press(screen.getByTestId("math-converter-unit-nm"));
    expect(onPickUnit).toHaveBeenCalledWith("nm");
  });
});
