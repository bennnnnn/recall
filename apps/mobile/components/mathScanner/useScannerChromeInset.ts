import { useMemo, useState } from "react";

import { scanChromeInset } from "@/lib/math/scannerRegion";

type Size = { width: number; height: number };

/**
 * The crop frame's room between the scanner's chrome. The controls have fixed
 * sizes; the photo disclosure above them wraps with the reader's text size, so
 * the chrome reports its height once it lays out and the frame moves clear of
 * it (the chrome lifts its error banner by the same amount).
 */
export function useScannerChromeInset({ width, height }: Size, safe: { top: number; bottom: number }) {
  const [disclosureHeight, setDisclosureHeight] = useState(0);
  const { top, bottom } = safe;
  const inset = useMemo(
    () => scanChromeInset(width, height, { top, bottom }, disclosureHeight),
    [width, height, top, bottom, disclosureHeight],
  );
  return { inset, disclosureHeight, onDisclosureLayout: setDisclosureHeight };
}
