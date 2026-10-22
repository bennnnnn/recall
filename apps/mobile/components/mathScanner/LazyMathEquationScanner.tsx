/**
 * The scanner (camera, live text detection, crop and read-back review) loads
 * the first time it is opened, not with the chat screen, and only then asks
 * for the camera permission state. Once open it stays mounted, as the eager
 * scanner always was, so closing still plays its own dismissal.
 */
import { lazy, Suspense, useState, type ComponentProps } from "react";

import type { MathEquationScanner } from "@/components/MathEquationScanner";

type Props = ComponentProps<typeof MathEquationScanner>;

const MathEquationScannerLazy = lazy(() =>
  import("@/components/MathEquationScanner").then((m) => ({ default: m.MathEquationScanner })),
);

export function LazyMathEquationScanner(props: Props) {
  const [opened, setOpened] = useState(props.visible);
  if (props.visible && !opened) setOpened(true);
  if (!opened) return null;
  return (
    <Suspense fallback={null}>
      <MathEquationScannerLazy {...props} />
    </Suspense>
  );
}
