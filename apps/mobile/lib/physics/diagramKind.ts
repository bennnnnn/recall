/**
 * Scenes with no moving bodies: the server sends the network, the optical
 * layout or the wave frames, and `components/rich/diagrams/` lays them out.
 * Everything else in a `simulation` fence is `SimulationBlock`'s.
 */
export const DIAGRAM_KINDS = ["circuit", "rays", "wave"] as const;
export type DiagramKind = (typeof DIAGRAM_KINDS)[number];

/** The diagram kind a fence's JSON names, or null for a body scene or bad JSON. */
export function diagramKind(raw: string): DiagramKind | null {
  try {
    const data = JSON.parse(raw.trim()) as { type?: unknown } | null;
    const type = data && typeof data === "object" ? data.type : undefined;
    return DIAGRAM_KINDS.includes(type as DiagramKind)
      ? (type as DiagramKind)
      : null;
  } catch {
    return null;
  }
}
