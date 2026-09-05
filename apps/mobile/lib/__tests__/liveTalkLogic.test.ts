import {
  LIVE_TALK_CONNECT_WARMUP_MS,
  LIVE_TALK_PLAYBACK_TAIL_MS,
  liveTalkErrorGate,
  liveTalkGate,
  liveTalkOrbAction,
  liveTalkOrbMode,
  liveTalkShouldAttachSession,
  liveTalkShouldCloseOnChatChange,
  liveTalkDataChannelText,
  liveTalkMuteA11yKey,
  liveTalkShowsSideChrome,
  liveTalkLocalMicEnabled,
  liveTalkShouldCreateResponse,
  isLikelyAssistantEcho,
  type LiveTalkStatus,
} from "@/lib/liveTalkLogic";

const proReady: LiveTalkStatus = {
  enabled: true,
  entitled: true,
  remaining: 12,
  limit: 30,
};

describe("liveTalkGate", () => {
  it("blocks offline before status", () => {
    expect(liveTalkGate(proReady, true)).toBe("offline");
  });

  it("opens upgrade when free (limit 0)", () => {
    expect(
      liveTalkGate({ enabled: true, entitled: false, remaining: 0, limit: 0 }, false),
    ).toBe("upgrade");
  });

  it("opens limit when Pro is exhausted", () => {
    expect(
      liveTalkGate({ enabled: true, entitled: true, remaining: 0, limit: 30 }, false),
    ).toBe("limit");
  });

  it("allows a remaining Pro turn", () => {
    expect(liveTalkGate(proReady, false)).toBe("ok");
  });
});

describe("liveTalkShouldAttachSession", () => {
  it("drops the session when close or a newer open bumped the generation", () => {
    expect(liveTalkShouldAttachSession(3, 3)).toBe(true);
    expect(liveTalkShouldAttachSession(3, 4)).toBe(false);
  });
});

describe("liveTalkShouldCloseOnChatChange", () => {
  it("closes only when the bound chat is left", () => {
    expect(liveTalkShouldCloseOnChatChange("chat-a", "chat-b")).toBe(true);
    expect(liveTalkShouldCloseOnChatChange("chat-a", "chat-a")).toBe(false);
    expect(liveTalkShouldCloseOnChatChange("chat-a", null)).toBe(true);
    expect(liveTalkShouldCloseOnChatChange(null, "chat-b")).toBe(false);
  });
});

describe("liveTalkDataChannelText", () => {
  it("reads string payloads and UTF-8 bytes", () => {
    expect(liveTalkDataChannelText('{"type":"response.done"}')).toBe('{"type":"response.done"}');
    expect(liveTalkDataChannelText(new TextEncoder().encode('{"type":"x"}'))).toBe('{"type":"x"}');
    expect(liveTalkDataChannelText(null)).toBeNull();
  });
});

describe("liveTalkErrorGate", () => {
  it("maps 403 to upgrade and 429 to limit", () => {
    expect(liveTalkErrorGate({ status: 403 })).toBe("upgrade");
    expect(liveTalkErrorGate({ status: 429 })).toBe("limit");
  });

  it("maps a missing WebRTC native module to unavailable", () => {
    expect(liveTalkErrorGate(new Error("webrtc_unavailable"))).toBe("unavailable");
  });

  it("maps a missing Realtime server key to unconfigured", () => {
    expect(liveTalkErrorGate({ status: 503 })).toBe("unconfigured");
  });
});

describe("liveTalkOrbMode", () => {
  it("maps listen vs speak without using on-screen copy", () => {
    expect(liveTalkOrbMode("recording")).toBe("listen");
    expect(liveTalkOrbMode("speaking")).toBe("speak");
    expect(liveTalkOrbMode("thinking")).toBe("think");
    expect(liveTalkOrbMode("idle")).toBe("idle");
  });
});

describe("liveTalkOrbAction", () => {
  it("does not mute from the orb; mic control owns mute", () => {
    expect(liveTalkOrbAction("speaking")).toBe("none");
    expect(liveTalkOrbAction("thinking")).toBe("cancelThink");
    expect(liveTalkOrbAction("recording")).toBe("finishListen");
    expect(liveTalkOrbAction("idle")).toBe("begin");
    expect(liveTalkMuteA11yKey(false)).toBe("chat.live_talk_mute_a11y");
    expect(liveTalkMuteA11yKey(true)).toBe("chat.live_talk_unmute_a11y");
    expect(liveTalkShowsSideChrome("")).toBe(true);
    expect(liveTalkShowsSideChrome("  ")).toBe(true);
    expect(liveTalkShowsSideChrome("hello")).toBe(false);
  });
});

describe("liveTalkLocalMicEnabled", () => {
  it("closes capture while the assistant is playing even if the user is not muted", () => {
    expect(liveTalkLocalMicEnabled(false, false)).toBe(true);
    expect(liveTalkLocalMicEnabled(false, true)).toBe(false);
    expect(liveTalkLocalMicEnabled(true, false)).toBe(false);
  });
});

describe("liveTalkShouldCreateResponse", () => {
  it("uses a connect warmup and a short playback tail before the mic reopens", () => {
    expect(LIVE_TALK_CONNECT_WARMUP_MS).toBe(1_500);
    expect(LIVE_TALK_PLAYBACK_TAIL_MS).toBe(500);
  });

  it("does not create a model turn from connect noise or assistant echo", () => {
    expect(
      liveTalkShouldCreateResponse({
        sessionReadyForTurns: false,
        assistantSpeaking: false,
        userMuted: false,
        acceptedUserUtterance: true,
      }),
    ).toBe(false);
    expect(
      liveTalkShouldCreateResponse({
        sessionReadyForTurns: true,
        assistantSpeaking: true,
        userMuted: false,
        acceptedUserUtterance: true,
      }),
    ).toBe(false);
    expect(
      liveTalkShouldCreateResponse({
        sessionReadyForTurns: true,
        assistantSpeaking: false,
        userMuted: false,
        acceptedUserUtterance: false,
      }),
    ).toBe(false);
    expect(
      liveTalkShouldCreateResponse({
        sessionReadyForTurns: true,
        assistantSpeaking: false,
        userMuted: false,
        acceptedUserUtterance: true,
      }),
    ).toBe(true);
  });
});

describe("isLikelyAssistantEcho", () => {
  it("drops speaker-bleed fragments of the last assistant line", () => {
    expect(
      isLikelyAssistantEcho("Nice", "Nice to hear from you. What's on your mind today?"),
    ).toBe(true);
    expect(isLikelyAssistantEcho("what's the weather", "Nice to hear from you")).toBe(false);
  });
});
