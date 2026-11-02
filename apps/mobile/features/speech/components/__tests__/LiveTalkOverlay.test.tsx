import { AccessibilityInfo, Keyboard } from "react-native";
import { fireEvent, render } from "@testing-library/react-native";

import { DrawerProvider } from "@/contexts/DrawerContext";
import { LiveTalkOverlay } from "@/features/speech/components/LiveTalkOverlay";
import type { LiveTalkPhase } from "@/features/speech/model/liveTalkLogic";

jest.mock("@/lib/motion", () => ({
  useReduceMotion: () => true,
  Motion: { duration: { soft: 200, snappy: 200 }, easing: { inOut: undefined, in: undefined, out: undefined } },
}));

jest.mock("expo-linear-gradient", () => {
  const { View } = jest.requireActual("react-native") as typeof import("react-native");
  return { LinearGradient: View };
});

function makeCall(phase: LiveTalkPhase = "recording") {
  return {
    phase,
    voicePlaying: false,
    muted: false,
    toggle: jest.fn(),
    toggleMute: jest.fn(),
    close: jest.fn(),
  };
}

const base = { visible: true, headerInset: 96, bottomInset: 34 };

describe("LiveTalkOverlay", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("leaves the header strip open, takes it while the drawer hides the header, and runs to the bottom", async () => {
    const controls = { open: jest.fn(), close: jest.fn(), isOpenNow: () => false };
    const call = makeCall();
    const view = await render(
      <DrawerProvider controls={controls} isOpen={false}>
        <LiveTalkOverlay {...base} call={call} />
      </DrawerProvider>,
    );
    expect(view.getByTestId("live-talk-overlay")).toHaveStyle({ top: 96, bottom: 0 });

    await view.rerender(
      <DrawerProvider controls={controls} isOpen>
        <LiveTalkOverlay {...base} call={call} />
      </DrawerProvider>,
    );
    expect(view.getByTestId("live-talk-overlay")).toHaveStyle({ top: 0, bottom: 0 });
  });

  it("puts mute and end where the composer row was, and only end closes the call", async () => {
    const call = makeCall("speaking");
    const view = await render(<LiveTalkOverlay {...base} call={call} />);

    expect(view.getByTestId("live-talk-controls")).toBeTruthy();
    await fireEvent.press(view.getByTestId("live-talk-mute"));
    await fireEvent.press(view.getByTestId("live-talk-orb"));
    expect(call.toggleMute).toHaveBeenCalledTimes(1);
    expect(call.close).not.toHaveBeenCalled();

    await fireEvent.press(view.getByTestId("live-talk-close"));
    expect(call.close).toHaveBeenCalledTimes(1);
  });

  it("puts the keyboard away when the call opens", async () => {
    const dismiss = jest.spyOn(Keyboard, "dismiss");
    await render(<LiveTalkOverlay {...base} call={makeCall()} />);
    expect(dismiss).toHaveBeenCalled();
    dismiss.mockRestore();
  });

  it("does not pause from the orb and has no Listening/Speaking copy", async () => {
    const call = makeCall("speaking");
    const { getByTestId, queryByText } = await render(<LiveTalkOverlay {...base} call={call} />);

    expect(queryByText("chat.live_talk_speaking")).toBeNull();
    expect(queryByText("chat.live_talk_listening")).toBeNull();
    await fireEvent.press(getByTestId("live-talk-orb"));
    expect(call.toggle).not.toHaveBeenCalled();
  });

  it("names the orb's mode for listening and speaking, with the eyes on the face", async () => {
    const listen = await render(<LiveTalkOverlay {...base} call={makeCall("recording")} />);
    expect(listen.getByTestId("live-talk-orb-listen")).toBeTruthy();
    expect(listen.getByTestId("live-talk-orb-eyes")).toBeTruthy();
    const speak = await render(<LiveTalkOverlay {...base} call={makeCall("speaking")} />);
    expect(speak.getByTestId("live-talk-orb-speak")).toBeTruthy();
    expect(speak.getByTestId("live-talk-orb-eyes")).toBeTruthy();
  });

  // S7.13: one label served listening and speaking, and no change was announced.
  it("gives the orb a distinct screen-reader label for listening, thinking and speaking", async () => {
    const labels: (string | undefined)[] = [];
    for (const phase of ["recording", "thinking", "speaking"] as const) {
      const view = await render(<LiveTalkOverlay {...base} call={makeCall(phase)} />);
      labels.push(view.getByTestId("live-talk-orb").props.accessibilityLabel);
      await view.unmount();
    }
    expect(labels).toEqual([
      "chat.live_talk_listening_a11y",
      "chat.live_talk_thinking_a11y",
      "chat.live_talk_speaking_a11y",
    ]);
  });

  it("announces each phase change to the screen reader, with no on-screen copy", async () => {
    const announce = jest.spyOn(AccessibilityInfo, "announceForAccessibility");
    const view = await render(<LiveTalkOverlay {...base} call={makeCall("recording")} />);
    await view.rerender(<LiveTalkOverlay {...base} call={makeCall("thinking")} />);
    await view.rerender(<LiveTalkOverlay {...base} call={makeCall("speaking")} />);
    expect(announce.mock.calls.map(([text]) => text)).toEqual([
      "chat.live_talk_listening_a11y",
      "chat.live_talk_thinking_a11y",
      "chat.live_talk_speaking_a11y",
    ]);
    expect(view.queryByText("chat.live_talk_speaking_a11y")).toBeNull();
    announce.mockRestore();
  });
});
