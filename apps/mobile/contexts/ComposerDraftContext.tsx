import {
  createContext,
  useContext,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type MutableRefObject,
  type ReactNode,
  type SetStateAction,
} from "react";

import {
  COMPOSER_NEW_THREAD_KEY,
  adoptNewComposerThread,
  takeThreadDraft,
} from "@/lib/chat/composerThreadDraft";

type ComposerDraftApi = {
  setInput: Dispatch<SetStateAction<string>>;
  inputRef: MutableRefObject<string>;
  switchThread: (nextKey: string) => void;
  adoptComposerThread: (nextKey: string) => void;
  saveDraftForThread: (key: string, text: string) => void;
  getThreadKey: () => string;
};

type ComposerDraftValue = {
  input: string;
};

const ComposerDraftApiContext = createContext<ComposerDraftApi | null>(null);
const ComposerDraftValueContext = createContext<ComposerDraftValue | null>(null);

/** Owns composer text so keystrokes do not re-render ChatScreen / the message list. */
export function ComposerDraftProvider({ children }: { children: ReactNode }) {
  const [input, setInput] = useState("");
  const inputRef = useRef(input);
  inputRef.current = input;
  const draftsRef = useRef(new Map<string, string>());
  const threadKeyRef = useRef(COMPOSER_NEW_THREAD_KEY);

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
      },
      adoptComposerThread: (nextKey: string) => {
        threadKeyRef.current = adoptNewComposerThread(
          draftsRef.current,
          threadKeyRef.current,
          nextKey,
          inputRef.current,
        );
      },
      saveDraftForThread: (key: string, text: string) => {
        draftsRef.current.set(key, text);
        if (threadKeyRef.current === key) {
          setInput(text);
        }
      },
      getThreadKey: () => threadKeyRef.current,
    }),
    [],
  );
  const value = useMemo<ComposerDraftValue>(() => ({ input }), [input]);

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
