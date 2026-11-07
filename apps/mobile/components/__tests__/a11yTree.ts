/**
 * Test helper over a rendered tree: accessible elements drawn inside another
 * accessible element. iOS hides them, but Android's TalkBack gives each one a
 * stop of its own and leaves its words out of the parent's description, so a
 * radio, an answer card or a digit row must hold none (see
 * components/rich/accessibleElement.tsx).
 */
type Node = { type: string; props: Record<string, unknown>; children: (Node | string)[] | null };

function name(node: Node): string {
  const id = node.props.testID ?? node.props.accessibilityLabel ?? node.type;
  return String(id);
}

/** "outer > inner" for each accessible element nested in another; empty when there are none. */
export function nestedAccessibleElements(tree: unknown): string[] {
  const found: string[] = [];
  const walk = (node: Node | Node[] | string | null, owner: string | null) => {
    if (node == null || typeof node === "string") return;
    if (Array.isArray(node)) {
      node.forEach((child) => walk(child, owner));
      return;
    }
    const accessible = node.props.accessible === true;
    if (accessible && owner !== null) found.push(`${owner} > ${name(node)}`);
    const next = accessible && owner === null ? name(node) : owner;
    (node.children ?? []).forEach((child) => walk(child, next));
  };
  walk(tree as Node | Node[] | null, null);
  return found;
}
