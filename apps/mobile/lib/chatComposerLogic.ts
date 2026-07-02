export const CHAT_HEADER_BAR_HEIGHT = 52;
export const CHAT_HEADER_FADE_EXTRA = 48;
export const CHAT_FEEDBACK_ROW_HEIGHT = 48;
export const CHAT_KEYBOARD_LIFT_EXTRA = 0;
export const CHAT_COMPOSER_MIN_BOTTOM_PAD = 10;
export const CHAT_EMPTY_MIN_HEIGHT = 160;

export type ModelOption = { id: string; label: string };

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
  models: Array<{ id: string; label: string; available: boolean; plan_access: "free" | "pro" }> | undefined;
  isPro: boolean;
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
    opts.push({ id, label: info.label || id });
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
  const showFeedbackRow = options.messagesLength > 0 && !options.streaming;
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

