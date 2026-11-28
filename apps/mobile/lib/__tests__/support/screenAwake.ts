import { activateKeepAwakeAsync, deactivateKeepAwake } from "expo-keep-awake";

/**
 * The keep-awake tags held now, as the (mocked) native module was told since the last
 * `jest.clearAllMocks()`: each activation not yet deactivated. `prefix` keeps one owner's
 * ("live-talk:", "dictation:", "picture:").
 */
export function heldAwakeTags(prefix = ""): string[] {
  const held = new Map<string, number>();
  const count = (tag: string | undefined, by: number) => {
    if (tag === undefined) return;
    held.set(tag, (held.get(tag) ?? 0) + by);
  };
  jest.mocked(activateKeepAwakeAsync).mock.calls.forEach(([tag]) => count(tag, 1));
  jest.mocked(deactivateKeepAwake).mock.calls.forEach(([tag]) => count(tag, -1));
  return [...held].filter(([tag, n]) => n > 0 && tag.startsWith(prefix)).map(([tag]) => tag);
}
