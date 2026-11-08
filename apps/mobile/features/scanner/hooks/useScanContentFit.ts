import { useEffect } from "react";

import { fitToContent, type ImageBox } from "@/features/scanner/model/contentFit";
import { readTextLines } from "@/features/scanner/model/readTextLines";
import { photoBoxToViewRegion, type ScanRegion } from "@/lib/math/scannerRegion";

/** A still on the crop screen: its file, its size, and where the live frame was in it. */
export type FitShot = { localUri: string; width: number; height: number; aim?: ImageBox | null };

type Args = {
  preview: FitShot | null;
  /** Where the still is drawn, as a region of the view. */
  previewFrame: ScanRegion | null;
  /** The crop frame (`useMathScannerCrop`). */
  crop: {
    resetRegion: (region: ScanRegion) => void;
    fitRegion: (region: ScanRegion) => void;
    adjustments: () => number;
  };
};

/**
 * Starts the crop frame on a still's problem. It opens where the student aimed (a camera
 * shot's live frame) or on the whole photo; once the phone has read the still's text, it
 * moves onto that text (`fitToContent`), unless the student has moved it in the meantime.
 * Nothing is sent until Solve.
 */
export function useScanContentFit({ preview, previewFrame, crop }: Args) {
  const { resetRegion, fitRegion, adjustments } = crop;
  useEffect(() => {
    if (!preview || !previewFrame) return;
    resetRegion(preview.aim ? photoBoxToViewRegion(preview.aim, previewFrame) : previewFrame);
    const before = adjustments();
    let current = true;
    void readTextLines(preview.localUri, preview).then((lines) => {
      if (!current || adjustments() !== before) return;
      const fit = fitToContent(lines, preview, preview.aim ?? null);
      if (fit) fitRegion(photoBoxToViewRegion(fit, previewFrame));
    });
    return () => {
      current = false;
    };
  }, [adjustments, fitRegion, preview, previewFrame, resetRegion]);
}
