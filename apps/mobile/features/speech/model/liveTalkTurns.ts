/**
 * The turns of a live talk call until each is saved: the user's line and the reply it
 * prompted, named by the user's input item (the realtime event's `item_id`).
 *
 * The line is transcribed beside the reply and often lands after it, sometimes after the
 * reply ended or the next utterance began. It was put down as the call's latest line, under
 * the reply; a turn saved before it came kept no line (and the server keeps no reply without
 * one), and the late line was saved as a turn of its own. Here each line joins its own turn,
 * a turn whose reply is done waits a little for its line, and turns are handed on to be saved
 * in the order they began.
 */

export type LiveTalkTurn = { id: string; userText: string; assistantText: string };

type OpenTurn = LiveTalkTurn & {
  /** The reply ended or was cut off: the turn is saved once its line is in. */
  replied: boolean;
  finished: boolean;
  wait: ReturnType<typeof setTimeout> | null;
};

/** How long a turn whose reply is done waits for the user's own line before it is saved without it. */
export const LIVE_TALK_USER_LINE_WAIT_MS = 5_000;

export function createLiveTalkTurns(save: (turn: LiveTalkTurn) => void) {
  /** Every turn not yet handed on, oldest first. */
  const open: OpenTurn[] = [];
  /** The turn being spoken: the last utterance's, or the reply's when no utterance began one. */
  let current: OpenTurn | null = null;

  const begin = (id: string): OpenTurn => {
    const turn: OpenTurn = { id, userText: "", assistantText: "", replied: false, finished: false, wait: null };
    open.push(turn);
    current = turn;
    return turn;
  };
  const speaking = (): OpenTurn => current ?? begin(String(Date.now()));

  /** Hand on every finished turn that no earlier, unfinished one holds back. */
  const release = () => {
    for (let head = open[0]; head?.finished; head = open[0]) {
      open.shift();
      const userText = head.userText.trim();
      const assistantText = head.assistantText.trim();
      if (userText || assistantText) save({ id: head.id, userText, assistantText });
    }
  };
  const finish = (turn: OpenTurn) => {
    if (turn.wait != null) clearTimeout(turn.wait);
    turn.wait = null;
    turn.finished = true;
    if (current === turn) current = null;
    release();
  };

  return {
    /** A new utterance. The turn before is saved now, unless its reply is done and it waits for its line. */
    utterance(id: string): void {
      if (current && !current.replied) finish(current);
      begin(id);
    },
    /** The open turn a user line belongs to: the one it names, or the one being spoken; null when none. */
    turnFor(turnId?: string): string | null {
      if (turnId === undefined) return speaking().id;
      return open.find((turn) => turn.id === turnId && !turn.finished)?.id ?? null;
    },
    /** The user's line for an open turn (`turnFor`); a turn whose reply is done is saved with it now. */
    user(turnId: string, text: string): void {
      const turn = open.find((candidate) => candidate.id === turnId && !candidate.finished);
      if (!turn) return;
      turn.userText = text;
      if (turn.replied) finish(turn);
    },
    /** The reply so far, for the turn being spoken; returns that turn's id. */
    assistant(text: string): string {
      const turn = speaking();
      turn.assistantText = text;
      return turn.id;
    },
    /** A reply began: it has a turn even when no utterance started one. */
    replyStarted(): void {
      speaking();
    },
    /** The reply ended or was cut off: the turn is saved when its line is in, or after the wait. */
    replied(): void {
      const turn = current;
      if (!turn || turn.replied) return;
      turn.replied = true;
      if (turn.userText) return finish(turn);
      turn.wait = setTimeout(() => finish(turn), LIVE_TALK_USER_LINE_WAIT_MS);
    },
    /** The turn being spoken, if any. */
    current: (): LiveTalkTurn | null => current,
    /** The call ended: every open turn is handed on now, in order. */
    finishAll(): void {
      for (const turn of [...open]) finish(turn);
    },
  };
}

/**
 * Runs the call's saves one after another. Saves sent together raced on the server: a later
 * turn could be written first (a chat's rows sort by when they were written), and both read the
 * chat as untitled and queued its title twice. The hang-up's end of the call waits behind them
 * too: it closes saving, so a save still queued would be refused.
 */
export function createInOrder() {
  let last: Promise<unknown> = Promise.resolve();
  return <T>(task: () => Promise<T>): Promise<T> => {
    const next = last.then(task);
    // The next waits for this one to settle; its caller meets the failure, if any.
    last = Promise.allSettled([next]);
    return next;
  };
}
