/**
 * The Live Talk overlay and its animated orb load the first time Live Talk
 * opens, not with the chat screen. After that the overlay stays mounted, so it
 * plays its own exit and draws nothing while closed, as it always did.
 */
import { lazy, Suspense, useState, type ComponentProps } from "react";

import type { LiveTalkOverlay } from "@/features/speech/components/LiveTalkOverlay";

type Props = ComponentProps<typeof LiveTalkOverlay>;

const LiveTalkOverlayLazy = lazy(() =>
  import("@/features/speech/components/LiveTalkOverlay").then((m) => ({ default: m.LiveTalkOverlay })),
);

export function LazyLiveTalkOverlay(props: Props) {
  const [opened, setOpened] = useState(props.visible);
  if (props.visible && !opened) setOpened(true);
  if (!opened) return null;
  return (
    <Suspense fallback={null}>
      <LiveTalkOverlayLazy {...props} />
    </Suspense>
  );
}
