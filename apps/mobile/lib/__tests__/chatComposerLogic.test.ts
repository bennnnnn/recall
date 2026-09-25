import {
  buildModelOptions,
  CHAT_ACTION_ROW_HEIGHT,
  COMPOSER_INPUT_MAX_HEIGHT,
  COMPOSER_INPUT_MIN_HEIGHT,
  composerInputFrameHeight,
  retainedComposerContentHeight,
  composerNativeInputTraits,
  composerShowsMic,
  composerShowsSend,
  computeChatLayoutMetrics,
  formatModelCostHint,
  isComposerMenuOverlayOpen,
  isModelSelectableInComposer,
  resolveSelectedModelLabel,
  shouldReserveComposerActionGap,
} from "@/lib/chat/composerLogic";
import { IMAGE_GEN_PENDING_ASSISTANT_ID } from "@/features/images/model/imageGenIntent";

describe("composerInputFrameHeight", () => {
  it("grows one line per Return and caps at the field max", () => {
    expect(composerInputFrameHeight("", 80)).toEqual({
      height: COMPOSER_INPUT_MIN_HEIGHT,
      overflows: false,
    });
    expect(composerInputFrameHeight("\n\n", 0).height).toBeGreaterThan(
      COMPOSER_INPUT_MIN_HEIGHT,
    );
    expect(composerInputFrameHeight("K\nk", 20).height).toBeGreaterThan(
      COMPOSER_INPUT_MIN_HEIGHT,
    );
    expect(composerInputFrameHeight("line\n".repeat(12), 400)).toEqual({
      height: COMPOSER_INPUT_MAX_HEIGHT,
      overflows: true,
    });
  });

  it("keeps a wrap height while the same draft changes and drops it on reset", () => {
    const stored = { revision: 2, height: 88 };
    expect(retainedComposerContentHeight(stored, 2, "hello world")).toBe(88);
    expect(retainedComposerContentHeight(stored, 2, "hello worlds")).toBe(88);
    expect(retainedComposerContentHeight(stored, 2, "")).toBe(0);
    expect(retainedComposerContentHeight(stored, 3, "hello world")).toBe(0);
    expect(retainedComposerContentHeight(null, 2, "hello world")).toBe(0);
  });
});

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

  it("isComposerMenuOverlayOpen reflects attach sheet", () => {
    expect(isComposerMenuOverlayOpen(false)).toBe(false);
    expect(isComposerMenuOverlayOpen(true)).toBe(true);
  });

  it("composer input is a messaging field until the math editor owns it", () => {
    expect(composerNativeInputTraits(false)).toEqual({
      autoCorrect: true,
      spellCheck: true,
      autoCapitalize: "sentences",
    });
    expect(composerNativeInputTraits(true)).toEqual({
      autoCorrect: false,
      spellCheck: false,
      autoCapitalize: "none",
    });
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

  it("computeChatLayoutMetrics holds composer-gap air only for the in-flight placeholder", () => {
    const idle = computeChatLayoutMetrics({
      insetsTop: 44,
      insetsBottom: 20,
      windowHeight: 800,
      keyboardHeight: 0,
      composerHeight: 100,
      attachmentExtra: 0,
      messagesLength: 2,
      streaming: false,
      lastMessageId: "msg-1",
    });
    expect(idle.headerMinimumHeight).toBe(96);
    expect(idle.headerInset).toBe(96);
    expect(idle.composerLift).toBe(0);
    expect(idle.composerBottomPad).toBe(20);
    expect(idle.listBottomPad).toBe(idle.composerClearance);

    const streaming = computeChatLayoutMetrics({
      insetsTop: 44,
      insetsBottom: 20,
      windowHeight: 800,
      keyboardHeight: 0,
      composerHeight: 100,
      attachmentExtra: 0,
      messagesLength: 2,
      streaming: true,
      lastMessageId: "streaming",
    });
    expect(streaming.listBottomPad).toBe(idle.composerClearance + CHAT_ACTION_ROW_HEIGHT);

    // Finalize still has streaming=true on the old signal, but icons already
    // live on the persisted row — do not keep the extra pad.
    const finalizing = computeChatLayoutMetrics({
      insetsTop: 44,
      insetsBottom: 20,
      windowHeight: 800,
      keyboardHeight: 0,
      composerHeight: 100,
      attachmentExtra: 0,
      messagesLength: 2,
      streaming: true,
      lastMessageId: "msg-1",
    });
    expect(finalizing.listBottomPad).toBe(idle.composerClearance);

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

    const withMathBar = computeChatLayoutMetrics({
      insetsTop: 44,
      insetsBottom: 20,
      windowHeight: 800,
      keyboardHeight: 0,
      composerHeight: 100,
      attachmentExtra: 0,
      mathBarExtra: 44,
      messagesLength: 0,
      streaming: false,
    });
    expect(withMathBar.composerBlockHeight).toBe(144);

    const grownHeader = computeChatLayoutMetrics({
      insetsTop: 44,
      insetsBottom: 20,
      windowHeight: 800,
      keyboardHeight: 0,
      composerHeight: 100,
      attachmentExtra: 0,
      messagesLength: 2,
      streaming: false,
      measuredHeaderHeight: 124,
    });
    expect(grownHeader.headerMinimumHeight).toBe(96);
    expect(grownHeader.headerInset).toBe(124);
    expect(grownHeader.emptyHeight).toBe(idle.emptyHeight - 28);

    const scaledHeader = computeChatLayoutMetrics({
      insetsTop: 44,
      insetsBottom: 20,
      windowHeight: 800,
      fontScale: 3,
      keyboardHeight: 0,
      composerHeight: 100,
      attachmentExtra: 0,
      messagesLength: 2,
      streaming: false,
    });
    expect(scaledHeader.headerMinimumHeight).toBeGreaterThan(96);
    expect(scaledHeader.headerInset).toBe(scaledHeader.headerMinimumHeight);
  });

  it("shouldReserveComposerActionGap only for in-flight placeholders", () => {
    expect(shouldReserveComposerActionGap("streaming")).toBe(true);
    expect(shouldReserveComposerActionGap(IMAGE_GEN_PENDING_ASSISTANT_ID)).toBe(true);
    expect(shouldReserveComposerActionGap("msg-1")).toBe(false);
    expect(shouldReserveComposerActionGap(undefined)).toBe(false);
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
