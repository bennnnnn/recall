import { render, screen } from "@testing-library/react-native";

import { LazyLiveTalkOverlay } from "@/features/speech/components/LazyLiveTalkOverlay";

const mockModuleLoads: string[] = [];

jest.mock("@/features/speech/components/LiveTalkOverlay", () => {
  const { createElement } = jest.requireActual<typeof import("react")>("react");
  const { Text } = jest.requireActual<typeof import("react-native")>("react-native");
  mockModuleLoads.push("overlay");
  return {
    LiveTalkOverlay: ({ visible, phase }: { visible: boolean; phase: string }) =>
      createElement(Text, { testID: "live-talk-overlay" }, `${visible ? "open" : "closed"} ${phase}`),
  };
});

const props = {
  phase: "recording" as const,
  meterLevel: 0.8,
  recording: true,
  headerInset: 0,
  composerClearance: 0,
  onToggle: jest.fn(),
};

describe("LazyLiveTalkOverlay", () => {
  it("loads the overlay when Live Talk first opens and keeps it for its exit", async () => {
    const view = await render(<LazyLiveTalkOverlay visible={false} {...props} />);
    expect(screen.queryByTestId("live-talk-overlay")).toBeNull();
    expect(mockModuleLoads).toEqual([]);

    await view.rerender(<LazyLiveTalkOverlay visible {...props} />);
    expect(await screen.findByText("open recording")).toBeOnTheScreen();

    await view.rerender(<LazyLiveTalkOverlay visible={false} {...props} phase="idle" />);
    expect(screen.getByTestId("live-talk-overlay")).toHaveTextContent("closed idle");
    expect(mockModuleLoads).toEqual(["overlay"]);
  });
});
