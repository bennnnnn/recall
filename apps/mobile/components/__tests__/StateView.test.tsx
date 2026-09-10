import { render } from "@testing-library/react-native";

import { StateView } from "@/components/StateView";
import { lightTheme as mockLightTheme } from "@/lib/theme";

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

jest.mock("@/lib/theme", () => ({
  ...jest.requireActual("@/lib/theme"),
  useTheme: () => mockLightTheme,
}));

jest.mock("@/lib/haptics", () => ({
  tap: jest.fn(),
}));

jest.mock("@/components/Icon", () => {
  const { Text } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    Icon: ({ name }: { name: string }) => <Text>{name}</Text>,
  };
});

describe("StateView", () => {
  it("uses a generic alert icon for errors, not a cloud-offline glyph", async () => {
    const { getByText, queryByText } = await render(
      <StateView variant="error" title="common.error" />,
    );

    expect(getByText("alert-circle-outline")).toBeTruthy();
    expect(queryByText("cloud-offline-outline")).toBeNull();
  });

  it("keeps an explicit connectivity icon when the caller passes one", async () => {
    const { getByText } = await render(
      <StateView variant="error" icon="cloud-offline-outline" message="drawer.cant_reach" />,
    );

    expect(getByText("cloud-offline-outline")).toBeTruthy();
  });
});
