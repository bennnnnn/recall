import {
  buildModelOptions,
  computeChatLayoutMetrics,
  isComposerMenuOverlayOpen,
  resolvePlanLabel,
  resolveSelectedModelLabel,
} from "@/lib/chatComposerLogic";

describe("chatComposerLogic", () => {
  it("buildModelOptions includes auto first when enabled", () => {
    const opts = buildModelOptions({
      autoEnabled: true,
      autoModelId: "auto",
      autoLabel: "Auto",
      modelEnabledSet: new Set(["free-chat", "smart-chat"]),
      labelFor: (id) => (id === "free-chat" ? "Free" : "Smart"),
    });
    expect(opts.map((o) => o.id)).toEqual(["auto", "free-chat", "smart-chat"]);
    expect(opts[0].label).toBe("Auto");
  });

  it("resolveSelectedModelLabel prefers auto label", () => {
    expect(
      resolveSelectedModelLabel("auto", "auto", "Auto", () => "Free"),
    ).toBe("Auto");
    expect(
      resolveSelectedModelLabel("free-chat", "auto", "Auto", () => "Free"),
    ).toBe("Free");
  });

  it("resolvePlanLabel picks pro or free label", () => {
    expect(resolvePlanLabel(true, "Pro", "Free")).toBe("Pro");
    expect(resolvePlanLabel(false, "Pro", "Free")).toBe("Free");
  });

  it("computeChatLayoutMetrics accounts for keyboard and feedback row", () => {
    const idle = computeChatLayoutMetrics({
      insetsTop: 44,
      insetsBottom: 20,
      windowHeight: 800,
      keyboardHeight: 0,
      composerHeight: 100,
      attachmentExtra: 0,
      messagesLength: 2,
      streaming: false,
    });
    expect(idle.composerLift).toBe(0);
    expect(idle.composerBottomPad).toBe(20);
    expect(idle.listBottomPad).toBeGreaterThan(idle.composerClearance);

    const keyboard = computeChatLayoutMetrics({
      insetsTop: 44,
      insetsBottom: 20,
      windowHeight: 800,
      keyboardHeight: 300,
      composerHeight: 100,
      attachmentExtra: 44,
      messagesLength: 0,
      streaming: true,
    });
    expect(keyboard.composerLift).toBe(300);
    expect(keyboard.composerBottomPad).toBe(0);
    expect(keyboard.composerBlockHeight).toBe(144);
  });

  it("isComposerMenuOverlayOpen reflects attach sheet or plan picker", () => {
    expect(isComposerMenuOverlayOpen(false, false)).toBe(false);
    expect(isComposerMenuOverlayOpen(true, false)).toBe(true);
    expect(isComposerMenuOverlayOpen(false, true)).toBe(true);
  });
});
