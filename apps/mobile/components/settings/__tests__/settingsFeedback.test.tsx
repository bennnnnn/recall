import { render } from "@testing-library/react-native";

import { SettingsFieldSheet } from "@/components/settings/SettingsFieldSheet";
import {
  makeSettingsStyles,
  SettingsInlinePicker,
  SettingsSwitchRow,
} from "@/components/settings/settingsUi";
import { lightTheme } from "@/lib/theme";

jest.mock("@expo/vector-icons", () => ({ Ionicons: "Ionicons" }));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@/components/AppSheet", () => {
  const { View: RNView } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    AppSheet: ({ children }: { children: React.ReactNode }) => <RNView>{children}</RNView>,
  };
});

const styles = makeSettingsStyles(lightTheme);

describe("settings action feedback", () => {
  it("replaces a saving switch with row-level progress", async () => {
    const { getByRole, queryByRole } = await render(
      <SettingsSwitchRow
        title="Memory"
        value
        disabled
        busy
        onValueChange={jest.fn()}
        styles={styles}
        theme={lightTheme}
      />,
    );

    expect(getByRole("progressbar")).toBeOnTheScreen();
    expect(queryByRole("switch")).toBeNull();
  });

  it("binds the visible title to the native switch", async () => {
    const onValueChange = jest.fn();
    const { getByLabelText, getByRole } = await render(
      <SettingsSwitchRow
        title="Memory"
        value
        onValueChange={onValueChange}
        styles={styles}
        theme={lightTheme}
      />,
    );

    const sw = getByRole("switch");
    expect(sw).toBe(getByLabelText("Memory"));
    expect(sw.props.accessibilityState).toEqual(
      expect.objectContaining({ checked: true, disabled: false }),
    );
  });

  it("marks inline pickers busy without hiding their current value", async () => {
    const { getByText, getByRole } = await render(
      <SettingsInlinePicker
        title="Tone"
        value="Balanced"
        options={[{ key: "balanced", label: "Balanced" }]}
        selectedKey="balanced"
        expanded={false}
        disabled
        busy
        onToggle={jest.fn()}
        onSelect={jest.fn()}
        styles={styles}
        theme={lightTheme}
      />,
    );

    expect(getByText("Balanced")).toBeOnTheScreen();
    expect(getByRole("button").props.accessibilityState).toEqual({
      expanded: false,
      disabled: true,
      busy: true,
    });
  });

  it("locks the field editor while its save is pending", async () => {
    const { getByLabelText, getByPlaceholderText } = await render(
      <SettingsFieldSheet
        visible
        title="Name"
        value="Ada"
        placeholder="Your name"
        onChangeText={jest.fn()}
        onClose={jest.fn()}
        onSave={jest.fn()}
        saving
      />,
    );

    expect(getByPlaceholderText("Your name").props.editable).toBe(false);
    expect(getByLabelText("settings.save").props.accessibilityState).toEqual({
      disabled: true,
      busy: true,
    });
  });
});
