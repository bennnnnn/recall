/**
 * A preview WebView whose web process the system ended (memory pressure, a crash in the
 * page's engine). iOS leaves the card blank and Android, with no handler, ends the app,
 * so every preview card (chart, Mermaid, chemistry, the HTML Run tab) passes both
 * handlers here: a loss loads the page again under a new key, and a second loss within
 * `PREVIEW_LOSS_WINDOW_MS` shows the card's Retry (`PreviewLostNote`), which starts over.
 * Counted in time, not reset by a load: a page that loads and then runs out of memory
 * would otherwise reload forever, and a chart that sat through two trips to the
 * background an hour apart still reloads by itself.
 */
import { useCallback, useMemo, useState } from "react";

/** Process losses the card recovers from on its own, within the window, before it asks for a Retry. */
const PREVIEW_PROCESS_RELOADS = 1;
/** Losses this far apart are separate events, each recovered from on its own. */
const PREVIEW_LOSS_WINDOW_MS = 60_000;

type Recovery = { losses: number[]; lost: boolean; mount: number };

type WebViewRecovery = {
  /** Part of the WebView's key: it changes on every reload, so the view mounts afresh. */
  mount: number;
  /** The page is gone and the card shows Retry in its place. */
  lost: boolean;
  retry: () => void;
  /** Spread onto the WebView. */
  handlers: { onContentProcessDidTerminate: () => void; onRenderProcessGone: () => void };
};

export function useWebViewRecovery(): WebViewRecovery {
  const [state, setState] = useState<Recovery>({ losses: [], lost: false, mount: 0 });
  const onGone = useCallback(() => {
    const now = Date.now();
    setState((current) => {
      const losses = [...current.losses.filter((at) => now - at < PREVIEW_LOSS_WINDOW_MS), now];
      return losses.length > PREVIEW_PROCESS_RELOADS
        ? { ...current, losses, lost: true }
        : { losses, lost: false, mount: current.mount + 1 };
    });
  }, []);
  const retry = useCallback(() => {
    setState((current) => ({ losses: [], lost: false, mount: current.mount + 1 }));
  }, []);
  const handlers = useMemo(
    () => ({ onContentProcessDidTerminate: onGone, onRenderProcessGone: onGone }),
    [onGone],
  );
  return { mount: state.mount, lost: state.lost, retry, handlers };
}
