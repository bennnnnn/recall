import { useCallback, useEffect, useRef, type RefObject } from "react";

import { useAccountSession } from "@/contexts/accountSession";
import { onAppStateChange } from "@/lib/foregroundRefresh";
import { useLatestRef } from "@/lib/latestRef";
import { tokenSubject } from "@/lib/tokenSubject";

/** The file layer loads expo-file-system: only a read or a write needs it. */
const draftFile = () => import("@/features/chat/model/composerDraftFile");

/** Typing writes the file this long after the last key. */
const SAVE_AFTER_MS = 800;

type Options = {
  /** Every other thread's draft; the open thread's is the field's text. */
  draftsRef: RefObject<Map<string, string>>;
  threadKeyRef: RefObject<string>;
  inputRef: RefObject<string>;
  /** Puts a saved draft in the open thread's empty field. */
  restoreOpenDraft: (text: string) => void;
};

/** Whose drafts the file holds now (and for which sign-in), and whether this run has read them yet. */
type FileState = {
  owner: string | null;
  account: string | null;
  loaded: boolean;
  timer: ReturnType<typeof setTimeout> | null;
};

/**
 * Keeps the composer's drafts (each chat's, and New Chat's) on disk for the signed-in
 * account, and puts them back on the next run. Nothing is written before this account's
 * file is read, so a run that has not read it never writes over the drafts it holds.
 * Returns `saveSoon`: after typing settles, or at once when `now` (an emptied field is a
 * sent draft, which must not come back if the app is closed next); and `noteEdited`, for
 * each thread this run writes: its text is newer than the file's, even emptied.
 */
export function useSavedComposerDrafts({ draftsRef, threadKeyRef, inputRef, restoreOpenDraft }: Options) {
  const { account, getToken } = useAccountSession();
  const accountRef = useLatestRef(account);
  const file = useRef<FileState>({ owner: null, account: null, loaded: false, timer: null });
  const edited = useRef(new Set<string>());
  const noteEdited = useCallback((key: string) => { edited.current.add(key); }, []);

  const saveNow = useCallback(() => {
    const state = file.current;
    if (state.timer) clearTimeout(state.timer);
    state.timer = null;
    // A sign-out since: the drafts were that account's, and its file is gone.
    if (!state.owner || !state.loaded || state.account !== accountRef.current) return;
    const drafts = new Map(draftsRef.current);
    // The open thread's text is the field's, and the newest.
    drafts.delete(threadKeyRef.current);
    drafts.set(threadKeyRef.current, inputRef.current);
    const owner = state.owner;
    void draftFile().then((stored) => stored.writeComposerDrafts(owner, drafts));
  }, [draftsRef, threadKeyRef, inputRef, accountRef]);

  const saveSoon = useCallback((now = false) => {
    const state = file.current;
    if (state.timer) clearTimeout(state.timer);
    state.timer = now ? null : setTimeout(saveNow, SAVE_AFTER_MS);
    if (now) saveNow();
  }, [saveNow]);

  useEffect(() => {
    const token = account ? getToken() : null;
    const owner = token ? tokenSubject(token) : null;
    const state = file.current;
    Object.assign(state, { owner, account, loaded: false });
    edited.current.clear();
    if (!owner) return;
    let cancelled = false;
    void draftFile().then((stored) => stored.readComposerDrafts(owner)).then((saved) => {
      if (cancelled) return;
      const openKey = threadKeyRef.current;
      // A thread this run wrote (typed, emptied, sent) keeps its text; the open one's is its field's.
      const kept = [...saved].filter(([key]) => key !== openKey && !edited.current.has(key));
      // The file's drafts are older than this run's: they go first, and leave first at the cap. An
      // empty slot this run left without writing it (the field was empty at a switch) takes the file's.
      const drafts = new Map(kept);
      draftsRef.current.forEach((text, key) => {
        if (!text && drafts.has(key)) return;
        drafts.delete(key);
        drafts.set(key, text);
      });
      draftsRef.current.clear();
      drafts.forEach((text, key) => draftsRef.current.set(key, text));
      const open = saved.get(openKey);
      if (open && !edited.current.has(openKey) && !inputRef.current) restoreOpenDraft(open);
      state.loaded = true;
    });
    return () => { cancelled = true; };
  }, [account, getToken, draftsRef, threadKeyRef, inputRef, restoreOpenDraft]);

  // The phone may close the app at any time once it leaves the screen: what was typed goes now.
  useEffect(() => onAppStateChange((state) => {
    if (state !== "active") saveNow();
  }), [saveNow]);
  // So does leaving the chat screen.
  useEffect(() => saveNow, [saveNow]);

  return { saveSoon, noteEdited };
}
