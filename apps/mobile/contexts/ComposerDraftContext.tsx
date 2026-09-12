import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type MutableRefObject,
  type ReactNode,
  type SetStateAction,
} from "react";

import { subscribeComposerDraftReset } from "@/lib/chat/composerDraftReset";
import {
  COMPOSER_NEW_THREAD_KEY,
  adoptNewComposerThread,
  clearAllComposerDrafts,
  stashFailedSendDraft,
  takeThreadDraft,
} from "@/lib/chat/composerThreadDraft";

type ComposerDraftApi = {
  setInput: Dispatch<SetStateAction<string>>;
  inputRef: MutableRefObject<string>;
  switchThread: (nextKey: string) => void;
  adoptComposerThread: (nextKey: string) => void;
  stashFailedDraftForThread: (key: string, failedText: string) => void;
  resetForNewSession: () => void;
  getThreadKey: () => string;
};

type ComposerDraftValue = {
  input: string;
  /** Changes only when another draft/session becomes active, not on typing. */
  revision: number;
};

const ComposerDraftApiContext = createContext<ComposerDraftApi | null>(null);
const ComposerDraftValueContext = createContext<ComposerDraftValue | null>(null);

/** Owns composer text so keystrokes do not re-render ChatScreen / the message list. */
export function ComposerDraftProvider({ children }: { children: ReactNode }) {
  const [input, setInput] = useState("");
  const [revision, setRevision] = useState(0);
  const inputRef = useRef(input);
  inputRef.current = input;
  const draftsRef = useRef(new Map<string, string>());
  const threadKeyRef = useRef(COMPOSER_NEW_THREAD_KEY);

  const resetForNewSession = useCallback(() => {
    clearAllComposerDrafts(draftsRef.current);
    threadKeyRef.current = COMPOSER_NEW_THREAD_KEY;
    // switchThread may run in the same tick (useChatSend on session change).
    // setInput("") does not update this ref until the next render.
    inputRef.current = "";
    setInput("");
    setRevision((value) => value + 1);
  }, []);

  useEffect(() => subscribeComposerDraftReset(resetForNewSession), [resetForNewSession]);

  const api = useMemo<ComposerDraftApi>(
    () => ({
      setInput,
      inputRef,
      switchThread: (nextKey: string) => {
        const fromKey = threadKeyRef.current;
        const nextText = takeThreadDraft(
          draftsRef.current,
          fromKey,
          nextKey,
          inputRef.current,
        );
        if (fromKey === nextKey) return;
        threadKeyRef.current = nextKey;
        setInput(nextText);
        setRevision((value) => value + 1);
      },
      adoptComposerThread: (nextKey: string) => {
        threadKeyRef.current = adoptNewComposerThread(
          draftsRef.current,
          threadKeyRef.current,
          nextKey,
          inputRef.current,
        );
      },
      stashFailedDraftForThread: (key: string, failedText: string) => {
        if (threadKeyRef.current === key) return;
        stashFailedSendDraft(draftsRef.current, key, failedText);
      },
      resetForNewSession,
      getThreadKey: () => threadKeyRef.current,
    }),
    [resetForNewSession],
  );
  const value = useMemo<ComposerDraftValue>(() => ({ input, revision }), [input, revision]);

  return (
    <ComposerDraftApiContext.Provider value={api}>
      <ComposerDraftValueContext.Provider value={value}>{children}</ComposerDraftValueContext.Provider>
    </ComposerDraftApiContext.Provider>
  );
}

/** Stable setters/refs — safe in ChatScreen and useChatSend. */
export function useComposerDraftApi(): ComposerDraftApi {
  const ctx = useContext(ComposerDraftApiContext);
  if (!ctx) {
    throw new Error("useComposerDraftApi must be used within ComposerDraftProvider");
  }
  return ctx;
}

export function useComposerDraftApiOptional(): ComposerDraftApi | null {
  return useContext(ComposerDraftApiContext);
}

/** Live draft text — only ChatComposer (or tests) should subscribe. */
export function useComposerDraftValueOptional(): ComposerDraftValue | null {
  return useContext(ComposerDraftValueContext);
}
