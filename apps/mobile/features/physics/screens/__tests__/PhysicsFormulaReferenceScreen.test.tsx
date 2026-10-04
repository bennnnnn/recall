import { act, fireEvent, render } from "@testing-library/react-native";
import PhysicsFormulaReferenceScreen from "../PhysicsFormulaReferenceScreen";

jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
jest.mock("react-native-safe-area-context", () => ({ useSafeAreaInsets: () => ({ top: 0, bottom: 0 }) }));
jest.mock("@/lib/theme", () => ({
  useTheme: () => ({
    bg: "white",
    surface: "white",
    border: "gray",
    text: "black",
    textSecondary: "gray",
    textTertiary: "gray",
    primary: "blue",
    control: "white",
    danger: "red",
  }),
}));
jest.mock("@/components/rich/MathText", () => {
  const React = jest.requireActual("react");
  const { Text } = jest.requireActual("react-native");
  return { MathText: ({ latex }: { latex: string }) => React.createElement(Text, null, latex) };
});
jest.mock("@/ui/controls/StackBackButton", () => ({ StackBackButton: () => null }));
jest.mock("@/ui/controls/TextField", () => {
  const React = jest.requireActual("react");
  const { TextInput } = jest.requireActual("react-native");
  return { TextField: (props: Record<string, unknown>) => React.createElement(TextInput, props) };
});
jest.mock("@/ui/controls/SegmentedControl", () => {
  const React = jest.requireActual("react");
  const { Pressable, Text, View } = jest.requireActual("react-native");
  return {
    SegmentedControl: ({ segments, value, onChange, testID }: any) =>
      React.createElement(
        View,
        null,
        ...segments.map((segment: { key: string; label: string }) =>
          React.createElement(
            Pressable,
            { key: segment.key, testID: `${testID}-${segment.key}`, onPress: () => onChange(segment.key) },
            React.createElement(Text, null, `${segment.label}${segment.key === value ? " selected" : ""}`),
          ),
        ),
      ),
  };
});
jest.mock("@/ui/list/ListRow", () => {
  const React = jest.requireActual("react");
  const { Pressable, Text } = jest.requireActual("react-native");
  return {
    ListRow: ({ title, value, onPress, testID }: any) =>
      React.createElement(
        Pressable,
        { onPress, testID },
        React.createElement(Text, null, `${title} ${value ?? ""}`),
      ),
  };
});
jest.mock("@/ui/overlay/SelectMenu", () => ({ SelectMenu: () => null }));

describe("PhysicsFormulaReferenceScreen", () => {
  it("searches and filters formula cards, then opens the constants tab", async () => {
    const view = await render(<PhysicsFormulaReferenceScreen />);
    expect(view.getByTestId("physics-formula-measurement-1")).toBeTruthy();

    await act(() => fireEvent.changeText(view.getByTestId("physics-reference-search"), "Coulomb"));
    expect(view.getByTestId("physics-formula-electrostatics-2")).toBeTruthy();
    expect(view.queryByTestId("physics-formula-measurement-1")).toBeNull();

    await act(() => fireEvent.press(view.getByTestId("physics-reference-tab-constants")));
    expect(view.getByTestId("physics-constant-coulomb-constant")).toBeTruthy();
    expect(view.queryByTestId("physics-formula-electrostatics-2")).toBeNull();
  });

  it("filters by education level", async () => {
    const view = await render(<PhysicsFormulaReferenceScreen />);
    await act(() => fireEvent.press(view.getByTestId("physics-reference-level-undergraduate")));
    expect(view.getByTestId("physics-formula-rotational-dynamics-1")).toBeTruthy();
    expect(view.queryByTestId("physics-formula-measurement-1")).toBeNull();
  });

  it("shows typeset scientific notation in the constants tab", async () => {
    const view = await render(<PhysicsFormulaReferenceScreen />);
    await act(() => fireEvent.press(view.getByTestId("physics-reference-tab-constants")));
    expect(view.getByTestId("physics-constant-c")).toBeTruthy();
    expect(view.getByText(String.raw`c = 2.99792458 \times 10^{8}`)).toBeTruthy();
  });

  it("shows assumptions alongside context-dependent equations", async () => {
    const view = await render(<PhysicsFormulaReferenceScreen />);
    await act(() =>
      fireEvent.changeText(view.getByTestId("physics-reference-search"), "Projectile trajectory"),
    );
    expect(view.getByText("Assumes uniform gravity and negligible air resistance.")).toBeTruthy();
  });
});
