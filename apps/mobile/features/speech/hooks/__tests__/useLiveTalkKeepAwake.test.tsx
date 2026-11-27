import React from "react";
import { act, render } from "@testing-library/react-native";
import { activateKeepAwakeAsync, deactivateKeepAwake } from "expo-keep-awake";

import { useLiveTalk } from "@/features/speech/hooks/useLiveTalk";
import { createRealtimeVoiceSession } from "@/features/speech/model/realtimeVoice";
import { heldAwakeTags } from "@/lib/__tests__/support/screenAwake";

jest.mock("@/contexts/DrawerContext", () => ({
  useDrawerControls: () => ({ open: jest.fn(), close: jest.fn(), isOpenNow: () => false }),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => null }));
jest.mock("@/lib/reportRecoverableError", () => ({ reportRecoverableError: jest.fn() }));
jest.mock("@/ui/overlay/dialogs", () => ({ offerSettings: jest.fn(async () => true) }));
jest.mock("@/features/speech/model/liveTalkSfx", () => ({ playLiveTalkCue: jest.fn(async () => undefined) }));
jest.mock("@/features/speech/model/realtimeVoice", () => ({
  createRealtimeVoiceSession: jest.fn(),
  isRealtimeVoiceAvailable: () => true,
}));
jest.mock("@/lib/api", () => ({
  api: {
    liveTalkStatus: jest.fn(async () => ({
      enabled: true,
      entitled: true,
      remaining: 30,
      limit: 60,
      remaining_seconds: 1800,
      min_session_seconds: 60,
    })),
    endRealtimeSession: jest.fn(async () => ({})),
    persistRealtimeLiveTalkTurn: jest.fn(),
  },
}));

let live!: ReturnType<typeof useLiveTalk>;

function Probe() {
  const value = useLiveTalk({
    token: "tok",
    chatId: "chat-1",
    ensureChatId: async () => "chat-1",
    editThread: jest.fn(),
    isOffline: false,
    onUpgrade: jest.fn(),
    onScrollToLatest: jest.fn(),
    newMessageCountRef: { current: 0 },
    onFirstReply: jest.fn(),
    t: (key: string) => key,
  });
  React.useLayoutEffect(() => {
    live = value;
  });
  return null;
}

function callSession() {
  return { callId: "call-1", maxDurationSeconds: 600, setMuted: jest.fn(), cancelResponse: jest.fn(), close: jest.fn() };
}

const liveTalkTags = () => heldAwakeTags("live-talk:");

/** A hands-free call hung up when auto-lock took the app off the screen (review H4, 2026-11-27). */
describe("live talk keeps the screen on", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("holds the screen on for the call and lets it sleep when the call ends", async () => {
    jest.mocked(createRealtimeVoiceSession).mockResolvedValueOnce(callSession() as never);
    const view = await render(<Probe />);
    expect(activateKeepAwakeAsync).not.toHaveBeenCalled();

    await act(async () => {
      await live.open();
    });
    expect(live.visible).toBe(true);
    expect(liveTalkTags()).toHaveLength(1);
    const [tag] = liveTalkTags();
    expect(activateKeepAwakeAsync).toHaveBeenCalledWith(tag);

    await act(async () => {
      live.close();
    });
    expect(deactivateKeepAwake).toHaveBeenCalledWith(tag);
    expect(liveTalkTags()).toEqual([]);
    await view.unmount();
  });

  it("holds the screen on while the call connects, and lets it sleep when it fails", async () => {
    let fail!: (error: Error) => void;
    jest.mocked(createRealtimeVoiceSession).mockImplementationOnce(
      () => new Promise((_resolve, reject) => { fail = reject; }),
    );
    const view = await render(<Probe />);
    let opening!: Promise<void>;
    await act(async () => {
      opening = live.open();
    });
    // The sheet is up and WebRTC still connecting: the screen is held already.
    expect(live.visible).toBe(true);
    expect(liveTalkTags()).toHaveLength(1);
    const [tag] = liveTalkTags();

    await act(async () => {
      fail(new Error("webrtc_unavailable"));
      await opening;
    });
    expect(live.visible).toBe(false);
    expect(deactivateKeepAwake).toHaveBeenCalledWith(tag);
    expect(liveTalkTags()).toEqual([]);
    await view.unmount();
  });

  it("lets the screen sleep when the chat screen goes mid-call", async () => {
    jest.mocked(createRealtimeVoiceSession).mockResolvedValueOnce(callSession() as never);
    const view = await render(<Probe />);
    await act(async () => {
      await live.open();
    });
    const [tag] = liveTalkTags();
    await view.unmount();
    expect(deactivateKeepAwake).toHaveBeenCalledWith(tag);
    expect(liveTalkTags()).toEqual([]);
  });
});
