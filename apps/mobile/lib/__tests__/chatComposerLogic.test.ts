import {
  buildModelOptions,
  composerShowsMic,
  composerShowsSend,
  computeChatLayoutMetrics,
  formatModelCostHint,
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
      input_price_per_m: 0.14,
      output_price_per_m: 0.28,
      quota_multiplier: 1,
    },
    {
      id: "smart-chat",
      label: "Smart",
      available: false,
      plan_access: "pro" as const,
      input_price_per_m: 0.7,
      output_price_per_m: 2.5,
      quota_multiplier: 3.5,
    },
  ];

  const t = (key: string, params?: Record<string, string | number>) => {
    if (key === "settings.model_price_per_m" && params) {
      return `~$${params.input} in · ~$${params.output} out / 1M tokens`;
    }
    if (key === "settings.model_quota_multiplier" && params) {
      return `${params.multiplier}× daily quota`;
    }
    return key;
  };

  it("buildModelOptions includes auto first when enabled", () => {
    const opts = buildModelOptions({
      autoEnabled: true,
      autoModelId: "auto",
      autoLabel: "Auto",
      modelEnabledSet: new Set(["free-chat", "smart-chat"]),
      models: catalog,
      isPro: true,
      t,
    });
    expect(opts.map((o) => o.id)).toEqual(["auto", "free-chat"]);
    expect(opts[0].label).toBe("Auto");
    expect(opts[1].hint).toBeUndefined();
  });

  it("buildModelOptions tolerates missing catalog", () => {
    const opts = buildModelOptions({
      autoEnabled: true,
      autoModelId: "auto",
      autoLabel: "Auto",
      modelEnabledSet: new Set(["free-chat"]),
      models: undefined as unknown as typeof catalog,
      isPro: true,
    });
    expect(opts.map((o) => o.id)).toEqual(["auto"]);
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

  it("isComposerMenuOverlayOpen is false for modal attach sheet", () => {
    expect(isComposerMenuOverlayOpen(false)).toBe(false);
    expect(isComposerMenuOverlayOpen(true)).toBe(false);
  });

  it("composerShowsMic and composerShowsSend are mutually exclusive for typed text", () => {
    expect(
      composerShowsMic({
        voiceAvailable: true,
        voiceRecording: false,
        voiceTranscribing: false,
        hasSendableContent: false,
      }),
    ).toBe(true);
    expect(
      composerShowsSend({
        voiceRecording: false,
        voiceTranscribing: false,
        hasSendableContent: false,
      }),
    ).toBe(false);

    expect(
      composerShowsMic({
        voiceAvailable: true,
        voiceRecording: false,
        voiceTranscribing: false,
        hasSendableContent: true,
      }),
    ).toBe(false);
    expect(
      composerShowsSend({
        voiceRecording: false,
        voiceTranscribing: false,
        hasSendableContent: true,
      }),
    ).toBe(true);

    // Mid-dictation: mic only (plus cancel), never send.
    expect(
      composerShowsMic({
        voiceAvailable: true,
        voiceRecording: true,
        voiceTranscribing: false,
        hasSendableContent: true,
      }),
    ).toBe(true);
    expect(
      composerShowsSend({
        voiceRecording: true,
        voiceTranscribing: false,
        hasSendableContent: true,
      }),
    ).toBe(false);
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

    // Feedback-row clearance must be reserved during streaming too, so the list
    // does not jump when a reply lands and the feedback icons appear.
    const streaming = computeChatLayoutMetrics({
      insetsTop: 44,
      insetsBottom: 20,
      windowHeight: 800,
      keyboardHeight: 0,
      composerHeight: 100,
      attachmentExtra: 0,
      messagesLength: 2,
      streaming: true,
    });
    expect(streaming.listBottomPad).toBe(idle.listBottomPad);

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

  it("formatModelCostHint shows quota multiplier only, not token prices", () => {
    expect(
      formatModelCostHint(
        {
          input_price_per_m: 0.7,
          output_price_per_m: 2.5,
          quota_multiplier: 3.5,
        },
        t,
      ),
    ).toBe("3.5× daily quota");
    expect(
      formatModelCostHint(
        { input_price_per_m: 0.14, output_price_per_m: 0.28, quota_multiplier: 1 },
        t,
      ),
    ).toBeUndefined();
  });
});
