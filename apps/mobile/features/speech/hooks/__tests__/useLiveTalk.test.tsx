import React from "react";
import { BackHandler, Linking } from "react-native";
import { act, render } from "@testing-library/react-native";

import { useLiveTalk } from "@/features/speech/hooks/useLiveTalk";
import { createRealtimeVoiceSession } from "@/features/speech/model/realtimeVoice";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { confirmDialog } from "@/ui/overlay/dialogs";

let mockDrawerOpen = false;
const mockDrawerControls = { open: jest.fn(), close: jest.fn(), isOpenNow: () => mockDrawerOpen };
jest.mock("@/contexts/DrawerContext", () => ({ useDrawerControls: () => mockDrawerControls }));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => null }));
jest.mock("@/lib/reportRecoverableError", () => ({ reportRecoverableError: jest.fn() }));
jest.mock("@/ui/overlay/dialogs", () => ({ confirmDialog: jest.fn(async () => true) }));
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
    setMessages: jest.fn(),
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

describe("useLiveTalk microphone denial (F8.8)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("asks for the microphone with Open Settings instead of the generic unavailable", async () => {
    const openSettings = jest.spyOn(Linking, "openSettings").mockResolvedValue(undefined);
    (createRealtimeVoiceSession as jest.Mock).mockRejectedValueOnce({
      name: "SecurityError",
      message: "Permission denied.",
    });
    await render(<Probe />);
    await act(async () => {
      await live.open();
    });

    expect(confirmDialog).toHaveBeenCalledWith({
      title: "chat.live_talk_mic_permission_title",
      message: "chat.live_talk_mic_permission_body",
      cancelLabel: "common.cancel",
      confirmLabel: "chat.location_open_settings",
    });
    expect(reportRecoverableError).not.toHaveBeenCalled();
    expect(openSettings).toHaveBeenCalledTimes(1);
    expect(live.visible).toBe(false);
    openSettings.mockRestore();
  });

  it("still says unavailable when WebRTC itself is missing", async () => {
    (createRealtimeVoiceSession as jest.Mock).mockRejectedValueOnce(new Error("webrtc_unavailable"));
    await render(<Probe />);
    await act(async () => {
      await live.open();
    });

    expect(confirmDialog).not.toHaveBeenCalled();
    expect(reportRecoverableError).toHaveBeenCalledWith(null, "chat.live_talk_unavailable_body");
  });

  it("leaves Back to an open drawer, reading the drawer when Back is pressed", async () => {
    const backHandlers: (() => boolean | null | undefined)[] = [];
    const addListener = jest
      .spyOn(BackHandler, "addEventListener")
      .mockImplementation((_event, handler) => {
        backHandlers.push(() => handler({} as never));
        return { remove: jest.fn() };
      });
    (createRealtimeVoiceSession as jest.Mock).mockResolvedValueOnce({
      callId: null,
      maxDurationSeconds: null,
      setMuted: jest.fn(),
      cancelResponse: jest.fn(),
      close: jest.fn(),
    });
    await render(<Probe />);
    await act(async () => {
      await live.open();
    });
    expect(live.visible).toBe(true);
    const back = backHandlers.at(-1)!;

    // The drawer opened after Live Talk did: Back closes the drawer, not Live Talk.
    mockDrawerOpen = true;
    expect(back()).toBe(false);
    expect(live.visible).toBe(true);

    mockDrawerOpen = false;
    await act(async () => {
      expect(back()).toBe(true);
    });
    expect(live.visible).toBe(false);
    addListener.mockRestore();
  });
});
