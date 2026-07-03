import { useEffect, useMemo, useState } from "react";
import type { TFunction } from "i18next";

const MAX_VARIANTS = 4;
export const STREAM_STATUS_ROTATE_MS = 3200;

/** Collect translated labels for a stream phase (base key + `_1`, `_2`, …). */
export function streamStatusLabels(t: TFunction, phase: string): string[] {
  const labels: string[] = [];
  const baseKey = `chat.status.${phase}`;
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

export function useRotatingStreamStatus(
  phase: string | undefined,
  enabled: boolean,
  t: TFunction,
): string | null {
  const labels = useMemo(
    () => (phase ? streamStatusLabels(t, phase) : []),
    [phase, t],
  );
  const [tick, setTick] = useState(0);

  useEffect(() => {
    setTick(0);
    if (!enabled || labels.length <= 1) {
      return;
    }
    const id = setInterval(() => {
      setTick((value) => value + 1);
    }, STREAM_STATUS_ROTATE_MS);
    return () => clearInterval(id);
  }, [enabled, labels.length, phase]);

  if (!phase || labels.length === 0) {
    return null;
  }
  return pickRotatingStreamLabel(labels, tick);
}
