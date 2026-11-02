import { render, screen } from "@testing-library/react-native";

import { LazyLiveTalkOverlay } from "@/features/speech/components/LazyLiveTalkOverlay";

const mockModuleLoads: string[] = [];
const mockVisibleSeen: boolean[] = [];

jest.mock("@/features/speech/components/LiveTalkOverlay", () => {
  const { createElement } = jest.requireActual<typeof import("react")>("react");
  const { Text } = jest.requireActual<typeof import("react-native")>("react-native");
  mockModuleLoads.push("overlay");
  return {
    LiveTalkOverlay: ({ visible, call }: { visible: boolean; call: { phase: string } }) => {
      mockVisibleSeen.push(visible);
      return createElement(Text, { testID: "live-talk-overlay" }, `${visible ? "open" : "closed"} ${call.phase}`);
    },
  };
});

const call = {
  phase: "recording" as const,
  voicePlaying: false,
  muted: false,
  toggle: jest.fn(),
  toggleMute: jest.fn(),
  close: jest.fn(),
};
const props = { call, headerInset: 0, bottomInset: 0 };

describe("LazyLiveTalkOverlay", () => {
  it("loads the overlay when Live Talk first opens and keeps it for its exit", async () => {
    const view = await render(<LazyLiveTalkOverlay visible={false} {...props} />);
    expect(screen.queryByTestId("live-talk-overlay")).toBeNull();
    expect(mockModuleLoads).toEqual([]);

    await view.rerender(<LazyLiveTalkOverlay visible {...props} />);
    expect(await screen.findByText("open recording")).toBeOnTheScreen();
    // Mounted closed, then opened: its entrance animation runs the first time too.
    expect(mockVisibleSeen[0]).toBe(false);
    expect(mockVisibleSeen.at(-1)).toBe(true);

    await view.rerender(<LazyLiveTalkOverlay visible={false} {...props} call={{ ...call, phase: "idle" }} />);
    expect(screen.getByTestId("live-talk-overlay")).toHaveTextContent("closed idle");
    expect(mockModuleLoads).toEqual(["overlay"]);
  });
});
