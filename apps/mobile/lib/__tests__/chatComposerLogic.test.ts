import {
  buildModelOptions,
  computeChatLayoutMetrics,
  isComposerMenuOverlayOpen,
  isModelSelectableInComposer,
  resolveSelectedModelLabel,
} from "@/lib/chatComposerLogic";

describe("chatComposerLogic", () => {
  const catalog = [
    {
      id: "free-chat",
      label: "Free",
      available: true,
      plan_access: "free" as const,
    },
    {
      id: "smart-chat",
      label: "Smart",
      available: false,
      plan_access: "pro" as const,
    },
  ];

  it("buildModelOptions includes auto first when enabled", () => {
    const opts = buildModelOptions({
      autoEnabled: true,
      autoModelId: "auto",
      autoLabel: "Auto",
      modelEnabledSet: new Set(["free-chat", "smart-chat"]),
      models: catalog,
      isPro: true,
    });
    expect(opts.map((o) => o.id)).toEqual(["auto", "free-chat"]);
    expect(opts[0].label).toBe("Auto");
  });

  it("buildModelOptions omits unavailable and pro-locked models", () => {
    const opts = buildModelOptions({
      autoEnabled: false,
      autoModelId: "auto",
      autoLabel: "Auto",
      modelEnabledSet: new Set(["free-chat", "smart-chat"]),
      models: [
        ...catalog,
        {
          id: "pro-only",
          label: "Pro",
          available: true,
          plan_access: "pro" as const,
        },
      ],
      isPro: false,
    });
    expect(opts.map((o) => o.id)).toEqual(["free-chat"]);
  });

  it("isModelSelectableInComposer respects availability and plan", () => {
    expect(
      isModelSelectableInComposer(
        { available: false, plan_access: "free" },
        true,
      ),
    ).toBe(false);
    expect(
      isModelSelectableInComposer(
        { available: true, plan_access: "pro" },
        false,
      ),
    ).toBe(false);
    expect(
      isModelSelectableInComposer(
        { available: true, plan_access: "pro" },
        true,
      ),
    ).toBe(true);
  });

  it("resolveSelectedModelLabel prefers auto label", () => {
    expect(
      resolveSelectedModelLabel("auto", "auto", "Auto", () => "Free"),
    ).toBe("Auto");
    expect(
      resolveSelectedModelLabel("free-chat", "auto", "Auto", () => "Free"),
    ).toBe("Free");
  });

  it("isComposerMenuOverlayOpen reflects attach sheet", () => {
    expect(isComposerMenuOverlayOpen(false)).toBe(false);
    expect(isComposerMenuOverlayOpen(true)).toBe(true);
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
});
