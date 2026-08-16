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

type ComposerDraftApi = {
  setInput: Dispatch<SetStateAction<string>>;
  inputRef: MutableRefObject<string>;
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

  const api = useMemo<ComposerDraftApi>(() => ({ setInput, inputRef }), []);
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
