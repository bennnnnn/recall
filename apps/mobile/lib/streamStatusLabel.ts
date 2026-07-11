import { useEffect, useMemo, useState } from "react";
import type { TFunction } from "i18next";

const MAX_VARIANTS = 6;
export const STREAM_STATUS_ROTATE_MS = 3200;
const STATUS_DETAIL_MAX_CHARS = 44;

/** Bound the inline detail so the label stays one line on small screens. */
export function clipStreamStatusDetail(detail: string): string {
  const flattened = detail.replace(/\s+/g, " ").trim();
  if (flattened.length <= STATUS_DETAIL_MAX_CHARS) return flattened;
  return `${flattened.slice(0, STATUS_DETAIL_MAX_CHARS - 1).trimEnd()}…`;
}

/**
 * Collect translated labels for a stream phase (base key + `_1`, `_2`, …).
 * When the server sent activity context (e.g. the search query) and a
 * `<phase>_detail` template exists, that label leads the rotation.
 */
export function streamStatusLabels(
  t: TFunction,
  phase: string,
  detail?: string,
): string[] {
  const labels: string[] = [];
  const baseKey = `chat.status.${phase}`;
  if (detail) {
    const detailKey = `${baseKey}_detail`;
    const withDetail = t(detailKey, { detail: clipStreamStatusDetail(detail) });
    if (withDetail !== detailKey) {
      labels.push(withDetail);
    }
  }
  const base = t(baseKey);
  if (base !== baseKey) {
    labels.push(base);
  }
  for (let i = 1; i < MAX_VARIANTS; i += 1) {
    const key = `${baseKey}_${i}`;
    const label = t(key);
    if (label === key) {
      break;
    }
    labels.push(label);
  }
  return labels;
}

export function pickRotatingStreamLabel(labels: string[], tick: number): string | null {
  if (labels.length === 0) {
    return null;
  }
  return labels[tick % labels.length] ?? labels[0];
}

/** The generic "thinking" indicator (typing dots / rotating status label) would
 * just duplicate the "model is working" signal once live reasoning content is
 * already visible, so it's suppressed while reasoning is showing. */
export function shouldShowWaitingIndicator(options: {
  isStreaming: boolean;
  hasContent: boolean;
  showReasoning: boolean;
}): boolean {
  return options.isStreaming && !options.hasContent && !options.showReasoning;
}

/**
 * Starting variant for a phase. Detail labels always lead; otherwise start at
 * a random variant so consecutive turns don't open with identical strings.
 */
export function initialStreamStatusTick(
  labelCount: number,
  hasDetail: boolean,
  random: () => number = Math.random,
): number {
  if (hasDetail || labelCount <= 1) {
    return 0;
  }
  return Math.floor(random() * labelCount) % labelCount;
}

export function useRotatingStreamStatus(
  phase: string | undefined,
  enabled: boolean,
  t: TFunction,
  detail?: string,
): string | null {
  const labels = useMemo(
    () => (phase ? streamStatusLabels(t, phase, detail) : []),
    [phase, detail, t],
  );
  const [tick, setTick] = useState(0);

  useEffect(() => {
    setTick(initialStreamStatusTick(labels.length, Boolean(detail)));
    if (!enabled || labels.length <= 1) {
      return;
    }
    const id = setInterval(() => {
      setTick((value) => value + 1);
    }, STREAM_STATUS_ROTATE_MS);
    return () => clearInterval(id);
  }, [enabled, labels.length, phase, detail]);

  if (!phase || labels.length === 0) {
    return null;
  }
  return pickRotatingStreamLabel(labels, tick);
}
