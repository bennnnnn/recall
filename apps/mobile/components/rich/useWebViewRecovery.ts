/**
 * A preview WebView whose web process the system ended (memory pressure, a crash in the
 * page's engine). iOS leaves the card blank and Android, with no handler, ends the app,
 * so every preview card (chart, Mermaid, chemistry, the HTML Run tab) passes both
 * handlers here: the first loss loads the page again under a new key, and a second
 * shows the card's Retry (`PreviewLostNote`), which starts over.
 */
import { useCallback, useMemo, useState } from "react";

/** Process losses the card recovers from on its own before it asks for a Retry. */
const PREVIEW_PROCESS_RELOADS = 1;

type Recovery = { losses: number; mount: number };

type WebViewRecovery = {
  /** Part of the WebView's key: it changes on every reload, so the view mounts afresh. */
  mount: number;
  /** The page is gone and the card shows Retry in its place. */
  lost: boolean;
  retry: () => void;
  /** Spread onto the WebView. */
  handlers: { onContentProcessDidTerminate: () => void; onRenderProcessGone: () => void; onLoad: () => void };
};

export function useWebViewRecovery(): WebViewRecovery {
  const [state, setState] = useState<Recovery>({ losses: 0, mount: 0 });
  const onGone = useCallback(() => {
    setState((current) =>
      current.losses < PREVIEW_PROCESS_RELOADS
        ? { losses: current.losses + 1, mount: current.mount + 1 }
        : { ...current, losses: current.losses + 1 },
    );
  }, []);
  const retry = useCallback(() => {
    setState((current) => ({ losses: 0, mount: current.mount + 1 }));
  }, []);
  // A page that loaded again starts the count over: Retry is for two losses in a row, not
  // two trips to the background a chart sat through.
  const onLoad = useCallback(() => {
    setState((current) => (current.losses === 0 ? current : { ...current, losses: 0 }));
  }, []);
  const handlers = useMemo(
    () => ({ onContentProcessDidTerminate: onGone, onRenderProcessGone: onGone, onLoad }),
    [onGone, onLoad],
  );
  return {
    mount: state.mount,
    lost: state.losses > PREVIEW_PROCESS_RELOADS,
    retry,
    handlers,
  };
}
