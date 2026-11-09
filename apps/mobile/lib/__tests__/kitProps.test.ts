/**
 * Structural guard: every optional prop of a UI-kit component is passed by some screen.
 *
 * The kit had grown props no caller passed: three of Chip's four variants and ten of its
 * props, Sheet's onShow and animation, the date picker's min/max, Slider's onRelease, and
 * more. Each read as an option to keep working, and was built and tested for nothing. A prop
 * comes back when a caller needs it. Tests do not count as callers.
 */
import * as ts from "typescript";

import { appFiles, isTest, readSource, relative } from "@/lib/__tests__/support/sourceFiles";

/** Props a test or the platform passes, not a screen. */
const NOT_A_CALLERS_PROP = new Set(["children", "testID"]);

type Component = { name: string; file: string; optional: string[] };

function parse(file: string): ts.SourceFile {
  return ts.createSourceFile(file, readSource(file), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
}

/** The optional props of each component a kit file declares with a props type. */
function components(file: string, source: ts.SourceFile): Component[] {
  const types = new Map<string, ts.NodeArray<ts.TypeElement>>();
  source.forEachChild((node) => {
    if (ts.isTypeAliasDeclaration(node) && ts.isTypeLiteralNode(node.type)) types.set(node.name.text, node.type.members);
    if (ts.isInterfaceDeclaration(node)) types.set(node.name.text, node.members);
  });
  const found: Component[] = [];
  const consider = (name: string, fn: ts.SignatureDeclarationBase) => {
    const param = fn.parameters[0]?.type;
    if (!param) return;
    const members = ts.isTypeLiteralNode(param)
      ? param.members
      : ts.isTypeReferenceNode(param) && ts.isIdentifier(param.typeName)
        ? types.get(param.typeName.text)
        : undefined;
    if (!members) return;
    const optional = members.flatMap((member) =>
      ts.isPropertySignature(member) && member.questionToken && ts.isIdentifier(member.name) ? [member.name.text] : [],
    );
    found.push({ name, file, optional });
  };
  const visit = (node: ts.Node) => {
    if (ts.isFunctionDeclaration(node) && node.name && /^[A-Z]/.test(node.name.text)) consider(node.name.text, node);
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && /^[A-Z]/.test(node.name.text) && node.initializer) {
      let init: ts.Expression = node.initializer;
      if (ts.isCallExpression(init) && init.arguments[0]) init = init.arguments[0];
      if (ts.isArrowFunction(init) || ts.isFunctionExpression(init)) consider(node.name.text, init);
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return found;
}

/** For each JSX tag the app's screens draw: the props passed to it, or null after a spread. */
function usage(sources: ts.SourceFile[]): Map<string, Set<string> | null> {
  const used = new Map<string, Set<string> | null>();
  const visit = (node: ts.Node) => {
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      const tag = node.tagName.getText();
      const attrs = used.has(tag) ? used.get(tag) : new Set<string>();
      if (attrs !== null) {
        for (const prop of node.attributes.properties) {
          if (ts.isJsxSpreadAttribute(prop)) {
            used.set(tag, null);
            ts.forEachChild(node, visit);
            return;
          }
          attrs?.add(prop.name.getText());
        }
        used.set(tag, attrs ?? new Set());
      }
    }
    ts.forEachChild(node, visit);
  };
  for (const source of sources) visit(source);
  return used;
}

describe("UI kit props", () => {
  it("passes every optional prop a kit component offers somewhere", () => {
    const production = appFiles().filter((file) => !isTest(file));
    const sources = new Map(production.map((file) => [file, parse(file)]));
    const used = usage([...sources.values()]);
    const unpassed: string[] = [];
    for (const [file, source] of sources) {
      if (!relative(file).startsWith("ui/")) continue;
      for (const component of components(file, source)) {
        const attrs = used.get(component.name);
        // Not drawn anywhere by name, or handed props by a spread: nothing to read here.
        if (!attrs) continue;
        const never = component.optional.filter((prop) => !NOT_A_CALLERS_PROP.has(prop) && !attrs.has(prop));
        if (never.length) unpassed.push(`${relative(file)} <${component.name}>: ${never.join(", ")}`);
      }
    }
    expect(unpassed).toEqual([]);
  });
});
