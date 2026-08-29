import { render } from "@testing-library/react-native";

import { ActionBanner } from "@/components/ActionBanner";
import { Layer } from "@/lib/layer";

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 34, left: 0, right: 0 }),
}));

jest.mock("@/hooks/useResolvedColorScheme", () => ({
  useResolvedColorScheme: () => "light",
}));

jest.mock("@/lib/motion", () => {
  const actual = jest.requireActual("@/lib/motion") as typeof import("@/lib/motion");
  return {
    ...actual,
    useReduceMotion: () => true,
  };
});

describe("ActionBanner", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("renders an in-tree host instead of a native Modal", async () => {
    const { getByTestId, getByLabelText } = await render(
      <ActionBanner message="Saved" onDismiss={jest.fn()} />,
    );

    expect(getByTestId("action-banner-host")).toBeOnTheScreen();
    expect(getByTestId("action-banner-host")).toHaveStyle({
      position: "absolute",
      zIndex: Layer.toast,
    });
    expect(getByLabelText("Saved")).toBeOnTheScreen();
  });

  it("uses an assertive live region for errors", async () => {
    const { getByLabelText } = await render(
      <ActionBanner message="Could not save" tone="error" onDismiss={jest.fn()} />,
    );

    expect(getByLabelText("Could not save").props.accessibilityLiveRegion).toBe(
      "assertive",
    );
  });
});
