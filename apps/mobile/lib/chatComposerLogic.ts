export const CHAT_HEADER_BAR_HEIGHT = 52;
export const CHAT_HEADER_FADE_EXTRA = 48;
export const CHAT_FEEDBACK_ROW_HEIGHT = 48;
export const CHAT_KEYBOARD_LIFT_EXTRA = 0;
export const CHAT_COMPOSER_MIN_BOTTOM_PAD = 10;
export const CHAT_EMPTY_MIN_HEIGHT = 160;

export type ModelOption = { id: string; label: string; hint?: string };

export type ModelCostFields = {
  input_price_per_m: number | null;
  output_price_per_m: number | null;
  quota_multiplier?: number;
};

export type TranslateFn = (
  key: string,
  params?: Record<string, string | number>,
) => string;

function formatQuotaMultiplier(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

/** Daily-quota weight for model picker rows (no per-token pricing in the UI). */
export function formatModelCostHint(
  model: ModelCostFields,
  t: TranslateFn,
): string | undefined {
  const mult = model.quota_multiplier ?? 1;
  if (mult > 1.001) {
    return t("settings.model_quota_multiplier", {
      multiplier: formatQuotaMultiplier(mult),
    });
  }
  return undefined;
}

export function isModelSelectableInComposer(
  model: { available: boolean; plan_access: "free" | "pro" },
  isPro: boolean,
): boolean {
  if (!model.available) return false;
  if (!isPro && model.plan_access === "pro") return false;
  return true;
}

export function buildModelOptions(options: {
  autoEnabled: boolean;
  autoModelId: string;
  autoLabel: string;
  modelEnabledSet: Set<string>;
  models: Array<{
    id: string;
    label: string;
    available: boolean;
    plan_access: "free" | "pro";
    input_price_per_m?: number | null;
    output_price_per_m?: number | null;
    quota_multiplier?: number;
  }> | undefined;
  isPro: boolean;
  t?: TranslateFn;
}): ModelOption[] {
  const catalog = options.models ?? [];
  const byId = new Map(catalog.map((model) => [model.id, model]));
  const opts: ModelOption[] = [];
  if (options.autoEnabled) {
    opts.push({ id: options.autoModelId, label: options.autoLabel });
  }
  for (const id of options.modelEnabledSet) {
    const info = byId.get(id);
    if (!info || !isModelSelectableInComposer(info, options.isPro)) {
      continue;
    }
    opts.push({
      id,
      label: info.label || id,
      hint: options.t
        ? formatModelCostHint(
            {
              input_price_per_m: info.input_price_per_m ?? null,
              output_price_per_m: info.output_price_per_m ?? null,
              quota_multiplier: info.quota_multiplier,
            },
            options.t,
          )
        : undefined,
    });
  }
  return opts;
}

export function resolveSelectedModelLabel(
  selectedModel: string,
  autoModelId: string,
  autoLabel: string,
  labelFor: (id: string) => string | undefined,
): string {
  return selectedModel === autoModelId
    ? autoLabel
    : labelFor(selectedModel) || selectedModel;
}

export function isComposerMenuOverlayOpen(attachSheetOpen: boolean): boolean {
  return attachSheetOpen;
}

/** Mic when empty; send when there is text/attachment. Never both (except stop while streaming). */
export function composerShowsMic(options: {
  voiceAvailable: boolean;
  voiceRecording: boolean;
  voiceTranscribing: boolean;
  hasSendableContent: boolean;
}): boolean {
  if (!options.voiceAvailable || options.voiceTranscribing) return false;
  if (options.voiceRecording) return true;
  return !options.hasSendableContent;
}

export function composerShowsSend(options: {
  voiceRecording: boolean;
  voiceTranscribing: boolean;
  hasSendableContent: boolean;
}): boolean {
  if (options.voiceRecording || options.voiceTranscribing) return false;
  return options.hasSendableContent;
}

export type ChatLayoutMetrics = {
  headerInset: number;
  fadeHeight: number;
  composerLift: number;
  composerBottomPad: number;
  composerBlockHeight: number;
  composerClearance: number;
  listBottomPad: number;
  emptyHeight: number;
};

export function computeChatLayoutMetrics(options: {
  insetsTop: number;
  insetsBottom: number;
  windowHeight: number;
  keyboardHeight: number;
  composerHeight: number;
  attachmentExtra: number;
  messagesLength: number;
  streaming: boolean;
}): ChatLayoutMetrics {
  const headerInset = options.insetsTop + CHAT_HEADER_BAR_HEIGHT;
  const fadeHeight = headerInset + CHAT_HEADER_FADE_EXTRA;
  const composerLift =
    options.keyboardHeight > 0
      ? options.keyboardHeight + CHAT_KEYBOARD_LIFT_EXTRA
      : 0;
  const composerBottomPad =
    options.keyboardHeight > 0
      ? 0
      : Math.max(options.insetsBottom, CHAT_COMPOSER_MIN_BOTTOM_PAD);
  const composerBlockHeight = options.composerHeight + options.attachmentExtra;
  const composerClearance = composerBlockHeight + composerBottomPad + composerLift;
  // Reserve the feedback-row clearance whenever the thread has messages —
  // NOT only when idle. Toggling this on `!streaming` grew the list's bottom
  // padding the instant a stream ended; with maintainVisibleContentPosition
  // pinning the bottom, that shifted every message up ~48px right as the reply
  // landed (the feedback icons themselves fade in later, via the in-bubble
  // slot). Keeping it constant across streaming→idle removes that jump.
  const showFeedbackRow = options.messagesLength > 0;
  const listBottomPad =
    composerBlockHeight +
    composerBottomPad +
    composerLift +
    (showFeedbackRow ? CHAT_FEEDBACK_ROW_HEIGHT : 0);
  const emptyHeight = Math.max(
    CHAT_EMPTY_MIN_HEIGHT,
    options.windowHeight - headerInset - composerClearance,
  );

  return {
    headerInset,
    fadeHeight,
    composerLift,
    composerBottomPad,
    composerBlockHeight,
    composerClearance,
    listBottomPad,
    emptyHeight,
  };
}

