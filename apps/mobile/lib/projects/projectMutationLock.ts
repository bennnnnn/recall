import { useSyncExternalStore } from "react";
import { getSessionGeneration } from "@/lib/auth";

const pending = new Set<string>();
const listeners = new Set<() => void>();
let revision = 0;
const notify = () => {
  revision++;
  listeners.forEach((listener) => listener());
};
const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};
const snapshot = () => revision;

/** Keep one create/goal/export operation active across screen visits. */
export function useProjectMutationLock() {
  useSyncExternalStore(subscribe, snapshot);
  const session = getSessionGeneration();
  const key = (name: string) => `${session}:${name}`;
  return {
    pending: (name: string) => pending.has(key(name)),
    begin(name: string) {
      const ownedKey = key(name);
      if (session !== getSessionGeneration() || pending.has(ownedKey)) return null;
      pending.add(ownedKey);
      notify();
      return () => {
        if (pending.delete(ownedKey)) notify();
      };
    },
  };
}
