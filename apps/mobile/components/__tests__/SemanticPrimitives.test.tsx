import { StyleSheet } from "react-native";
import { render } from "@testing-library/react-native";

import { CountBadge } from "@/components/CountBadge";
import { StatusPill } from "@/components/StatusPill";
import { lightTheme as mockLightTheme } from "@/lib/theme";

jest.mock("@/lib/theme", () => ({
  ...jest.requireActual("@/lib/theme"),
  useTheme: () => mockLightTheme,
}));

describe("semantic primitives", () => {
  it("uses danger ink and grows count badges with Dynamic Type", async () => {
    const { getByText } = await render(
      <CountBadge count={120} max={99} tone="danger" />,
    );
    const label = getByText("99+");
    const badgeStyle = StyleSheet.flatten(label.parent?.props.style);
    const labelStyle = StyleSheet.flatten(label.props.style);

    expect(badgeStyle).toMatchObject({
      minWidth: 18,
      minHeight: 18,
      backgroundColor: mockLightTheme.danger,
    });
    expect(badgeStyle.height).toBeUndefined();
    expect(labelStyle.color).toBe(mockLightTheme.onDanger);
    expect(labelStyle.lineHeight).toBeUndefined();
  });

  it.each([
    ["interviewing", "accent", mockLightTheme.primaryLight, mockLightTheme.primaryDark],
    ["offer", "success", mockLightTheme.successLight, mockLightTheme.text],
    ["rejected", "neutral", mockLightTheme.surfaceAlt, mockLightTheme.textTertiary],
  ] as const)("maps %s to the %s status tone", async (label, tone, background, foreground) => {
    const { getByText } = await render(<StatusPill label={label} tone={tone} />);
    const text = getByText(label);
    const pillStyle = StyleSheet.flatten(text.parent?.props.style);
    const textStyle = StyleSheet.flatten(text.props.style);

    expect(pillStyle.backgroundColor).toBe(background);
    expect(pillStyle.height).toBeUndefined();
    expect(textStyle.color).toBe(foreground);
    expect(textStyle.lineHeight).toBeUndefined();
  });
});
