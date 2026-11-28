import { randomUUID } from "expo-crypto";

/**
 * The id a to-do create is sent under (`client_id`), kept while the same to-do is saved
 * again after a failure. A create whose answer was lost may have been made: sent again
 * under its id, the server returns that to-do and adds nothing (migration 0138). A save
 * that worked, or a to-do with other words, a date or a repeat, takes a new id.
 */
export type CreateAttempts = {
  /** The id for a create of `key` (the to-do as it is sent). */
  idFor: (key: string) => string;
  /** The create of `key` was made: the next one is another to-do. */
  made: (key: string) => void;
};

export function createAttempts(newId: () => string = randomUUID): CreateAttempts {
  let held: { key: string; id: string } | null = null;
  return {
    idFor(key) {
      if (held?.key !== key) held = { key, id: newId() };
      return held.id;
    },
    made(key) {
      if (held?.key === key) held = null;
    },
  };
}
