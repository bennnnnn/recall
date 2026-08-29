import { StyleSheet } from "react-native";
import { render } from "@testing-library/react-native";

import { SocialPostCard } from "@/components/rich/SocialPostCard";
import { lightTheme } from "@/lib/theme";

jest.mock("expo-clipboard", () => ({ setStringAsync: jest.fn() }));
jest.mock("expo-haptics", () => ({
  impactAsync: jest.fn(),
  notificationAsync: jest.fn(),
  selectionAsync: jest.fn(),
}));
jest.mock("@expo/vector-icons", () => ({ Ionicons: "Ionicons" }));
jest.mock("react-native-svg", () => {
  const { View } = jest.requireActual("react-native") as typeof import("react-native");
  return { __esModule: true, default: View, Svg: View, Path: View };
});
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

describe("SocialPostCard", () => {
  it("does not paint a brand left stripe (same chrome as the SMS draft)", async () => {
    const { getByText } = await render(
      <SocialPostCard
        platform="linkedin"
        text="Excited to share that we've shipped a small product improvement."
      />,
    );
    const label = getByText("rich.post_draft_linkedin");
    let node: { parent?: unknown; props?: { style?: unknown } } | undefined =
      label;
    let sawBrandAccent = false;
    while (node) {
      const flat = StyleSheet.flatten(node.props?.style);
      if (
        flat?.borderLeftColor === lightTheme.brand.linkedin ||
        flat?.borderLeftColor === lightTheme.primary
      ) {
        sawBrandAccent = true;
        break;
      }
      node = node.parent as typeof node;
    }
    expect(sawBrandAccent).toBe(false);
  });

  it("renders draft copy without a fake You / avatar row", async () => {
    const { getByText, queryByText } = await render(
      <SocialPostCard platform="linkedin" text="Shipped this week." />,
    );
    expect(getByText("Shipped this week.")).toBeTruthy();
    expect(queryByText("common.you")).toBeNull();
  });
});
