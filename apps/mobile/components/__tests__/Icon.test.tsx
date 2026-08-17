import { render } from "@testing-library/react-native";

import { Icon } from "@/components/Icon";
import { lightTheme as mockLightTheme } from "@/lib/theme";

// String mock is the proven pattern in this suite (CopyButton, MathView, …).
jest.mock("@expo/vector-icons", () => ({ Ionicons: "Ionicons" }));
jest.mock("@/lib/theme", () => ({
  ...jest.requireActual("@/lib/theme"),
  useTheme: () => mockLightTheme,
}));

describe("Icon", () => {
  it("renders the name as-is (outline standard — no forced fill)", async () => {
    const { getByTestId } = await render(<Icon name="trash-outline" testID="i" />);
    expect(getByTestId("i").props.name).toBe("trash-outline");
  });

  it("keeps a filled name when a call site passes one (active-state emphasis)", async () => {
    const { getByTestId } = await render(<Icon name="thumbs-up" testID="i" />);
    expect(getByTestId("i").props.name).toBe("thumbs-up");
  });

  it("defaults size to 20", async () => {
    const { getByTestId } = await render(<Icon name="copy-outline" testID="i" />);
    expect(getByTestId("i").props.size).toBe(20);
  });

  it("uses the ink color by default (true black in light)", async () => {
    const { getByTestId } = await render(<Icon name="copy-outline" testID="i" />);
    expect(getByTestId("i").props.color).toBe("#000000");
  });

  it("uses the danger ink when danger is set", async () => {
    const { getByTestId } = await render(<Icon name="trash-outline" danger testID="i" />);
    expect(getByTestId("i").props.color).toBe(mockLightTheme.danger);
  });

  it("respects an explicit color", async () => {
    const { getByTestId } = await render(<Icon name="copy-outline" color="#ff0000" testID="i" />);
    expect(getByTestId("i").props.color).toBe("#ff0000");
  });
});
