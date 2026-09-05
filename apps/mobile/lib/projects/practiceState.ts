import { getSessionGeneration } from "@/lib/auth";
let session = -1;
let pending = new Set<string>();
const listeners = new Set<() => void>();
function current() {
  if (session !== getSessionGeneration()) {
    session = getSessionGeneration();
    pending = new Set();
  }
  return pending;
}
export function isPracticePending(itemId: string) {
  return current().has(itemId);
}
export function subscribePractice(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
export function beginPractice(itemId: string, expectedSession: number): (() => void) | null {
  if (expectedSession !== getSessionGeneration()) return null;
  const owned = current();
  if (owned.has(itemId)) return null;
  owned.add(itemId);
  listeners.forEach((listener) => listener());
  return () => {
    owned.delete(itemId);
    if (expectedSession === getSessionGeneration()) listeners.forEach((listener) => listener());
  };
}
