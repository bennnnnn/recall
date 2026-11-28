import { useEffect, useId } from "react";

import { holdScreenAwake, releaseScreenAwake } from "@/lib/keepAwake";

/**
 * Keeps the screen on while `on` is true (`lib/keepAwake.ts`). `owner` names what holds
 * it ("live-talk", "dictation", "picture"); each mounted owner has its own tag, so one
 * ending never releases another's. Released when `on` turns false and when the owner
 * unmounts.
 */
export function useKeepAwakeWhile(owner: string, on: boolean): void {
  const id = useId();
  const tag = `${owner}:${id}`;
  useEffect(() => {
    if (!on) return;
    holdScreenAwake(tag);
    return () => releaseScreenAwake(tag);
  }, [tag, on]);
}
