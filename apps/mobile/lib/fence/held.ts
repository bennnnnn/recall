/**
 * A fence the server writes or rewrites after the stream (a scene, a molecule, a graph, a
 * calculator) is drawn only once the reply settles. One the model wrote mid-reply is not the
 * server's yet: finalize strikes it or puts the checked one in its place, and a picture the
 * reader saw first would vanish or change. Held, like the reminder and settings cards, until
 * then. The answer card still draws while streaming (its row's `drawsWhileStreaming`): the
 * reply copies the verified answer into it as it writes, and the card adds its check once the
 * reply settles (`AnswerBlock`'s `settled`).
 */
import { FENCES, type FenceId } from "@/lib/fence/registry";

const HELD: ReadonlySet<string> = new Set(
  FENCES.filter((spec) => spec.owner === "server" && !spec.drawsWhileStreaming).map((spec) => spec.id),
);

export function isHeldWhileStreaming(id: FenceId): boolean {
  return HELD.has(id);
}
