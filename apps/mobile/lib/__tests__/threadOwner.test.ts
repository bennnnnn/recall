/**
 * One owner of the chat thread (structure ticket ST-08): the list of messages on screen is
 * React state in `useChat`, and every change to it is a step of the turn reducer — the turn's
 * own frames, or a `thread_edit` another writer sends through `editThread`. Only `useChat`,
 * which holds the setter, and the reducer's command runner may touch the setter, and no other
 * file holds a list of messages in React state or a setter for one, so a second owner cannot
 * appear under a new name.
 *
 * Holders are read by type, not by spelling: a call that answers `[list, setter]` (useState,
 * useReducer, a hook wrapping either, under any import name) whose list is of messages, and a
 * name typed as a setter of one (one parameter taking a list or an updater of it, however its
 * type is aliased). A list is of messages when its element is a `Message`, a narrower type
 * (`Message & {…}`) included. (useChat.test.tsx checks the hook hands out no setter under any key.)
 */
import * as ts from "typescript";

declare const __dirname: string;

const ROOT = ts.sys.resolvePath(`${__dirname}/../..`);
const OWNERS = ["features/chat/hooks/useChat.ts", "features/chat/model/chatTurnEffects.ts"];
/** The setter by its own name, whatever its type says. */
const SETTER_NAME = /\bsetMessages\b/;
/** Reading the whole app's types takes seconds; more on a loaded machine. */
const PROGRAM_TIMEOUT_MS = 120_000;

function productionFiles(): string[] {
  return ["app", "components", "contexts", "features", "hooks", "lib", "ui"]
    .flatMap((dir) =>
      ts.sys.readDirectory(`${ROOT}/${dir}`, [".ts", ".tsx"], ["**/__tests__/**", "**/vendor/**"]),
    )
    .filter((file) => !file.endsWith(".d.ts"));
}

function compilerOptions(): ts.CompilerOptions {
  const parsed = ts.getParsedCommandLineOfConfigFile(`${ROOT}/tsconfig.json`, {}, {
    ...ts.sys,
    onUnRecoverableConfigFileDiagnostic: () => undefined,
  });
  return { ...parsed?.options, noEmit: true };
}

function parts(type: ts.Type): readonly ts.Type[] {
  return type.isUnion() ? type.types : [type];
}

/** Files of `files` holding a list of messages in React state, or a setter for one. */
function holdersByType(program: ts.Program, files: string[]): string[] {
  const checker = program.getTypeChecker();
  const types = program.getSourceFile(`${ROOT}/lib/api/types.ts`);
  const declaration = types?.statements.find(
    (node): node is ts.TypeAliasDeclaration => ts.isTypeAliasDeclaration(node) && node.name.text === "Message",
  );
  if (!declaration) throw new Error("lib/api/types.ts no longer declares Message");
  const message = checker.getTypeAtLocation(declaration.name);
  const vague = ts.TypeFlags.Any | ts.TypeFlags.Unknown | ts.TypeFlags.Never;

  const isList = (type: ts.Type): boolean =>
    parts(type).some((part) => {
      if (!checker.isArrayType(part)) return false;
      const [element] = checker.getTypeArguments(part as ts.TypeReference);
      return Boolean(element) && !(element.flags & vague) && checker.isTypeAssignableTo(element, message);
    });
  /** `[list, setter]`: the answer of useState, useReducer or a hook wrapping either. */
  const isState = (type: ts.Type): boolean => {
    if (!checker.isTupleType(type)) return false;
    const [state, set] = checker.getTypeArguments(type as ts.TypeReference);
    return Boolean(state && set) && isList(state) && set.getCallSignatures().length > 0;
  };
  /** One parameter that takes a list, or an updater answering one: SetStateAction's shape. */
  const isSetter = (type: ts.Type): boolean =>
    type.getCallSignatures().some((signature) => {
      if (signature.parameters.length !== 1) return false;
      const accepted = parts(checker.getTypeOfSymbol(signature.parameters[0]));
      return accepted.some(isList) &&
        accepted.some((part) => part.getCallSignatures().some((updater) => isList(updater.getReturnType())));
    });
  const isNamed = (node: ts.Node): node is ts.NamedDeclaration & { name: ts.Identifier } =>
    (ts.isParameter(node) || ts.isVariableDeclaration(node) || ts.isPropertySignature(node) ||
      ts.isPropertyDeclaration(node) || ts.isBindingElement(node)) && ts.isIdentifier(node.name);

  return files.filter((file) => {
    const source = program.getSourceFile(file);
    if (!source) throw new Error(`not in the program: ${file}`);
    const holds = (node: ts.Node): boolean =>
      (ts.isCallExpression(node) && isState(checker.getTypeAtLocation(node))) ||
      (isNamed(node) && isSetter(checker.getTypeAtLocation(node.name))) ||
      ts.forEachChild(node, holds) === true;
    return holds(source);
  });
}

describe("the chat thread's owner", () => {
  it("only useChat and the turn's command runner hold the thread's state or setter", () => {
    const files = productionFiles();
    const program = ts.createProgram({ rootNames: files, options: compilerOptions() });
    const byName = files.filter((file) => SETTER_NAME.test(ts.sys.readFile(file) ?? ""));
    const holders = [...new Set([...byName, ...holdersByType(program, files)])]
      .map((file) => file.slice(ROOT.length + 1))
      .sort();
    expect(holders).toEqual(OWNERS);
  }, PROGRAM_TIMEOUT_MS);

  // 2026-11-01: the old check read spellings, and these held a thread past it.
  it("reads a holder by type, under any spelling", () => {
    const header = [
      'import * as React from "react";',
      'import { useReducer, useRef, useState, useState as useLocal, type Dispatch, type SetStateAction } from "react";',
      'import type { Message } from "@/lib/api";',
      "type Thread = readonly Message[];",
    ].join("\n");
    const held = [
      "const [rows, setRows] = useState([] as Message[]);",
      "const [rows, setRows] = useState<Array<Message>>([]);",
      "const [rows, setRows] = useState<Thread>([]);",
      "const [rows, add] = useReducer((list: Message[], next: Message) => [...list, next], []);",
      "const [rows, setRows] = React.useState<(Message & { local?: boolean })[]>([]);",
      "const [rows, setRows] = useLocal<Message[]>([]);",
      "function useList<T>() { return useState<T[]>([]); }\nconst [rows, setRows] = useList<Message>();",
      "export function write(to: Dispatch<SetStateAction<Thread>>) { return to; }",
      "export type Props = { onRows: (next: SetStateAction<Message[]>) => void };",
    ];
    const kept = [
      "const [names, setNames] = useState<string[]>([]);",
      "const [count, setCount] = useState(0);",
      "const [rows, setRows] = useState<any[]>([]);",
      "const rows = useRef<Message[]>([]);",
      'export const editThread = (update: SetStateAction<Message[]>, source: "image_turn") => [update, source];',
      "export const edit = (update: (rows: Message[]) => Message[]) => update;",
      "declare function split(rows: Message[]): [Message[], Message[]];\nconst [head, tail] = split([]);",
    ];
    const probes = new Map(
      [...held, ...kept].map((body, index) => [`${ROOT}/features/probe${index}.tsx`, `${header}\n${body}\n`]),
    );
    const options = compilerOptions();
    const host = ts.createCompilerHost(options);
    const { fileExists, getSourceFile, readFile } = host;
    host.fileExists = (name) => probes.has(name) || fileExists.call(host, name);
    host.readFile = (name) => probes.get(name) ?? readFile.call(host, name);
    host.getSourceFile = (name, language, ...rest) => {
      const text = probes.get(name);
      return text === undefined
        ? getSourceFile.call(host, name, language, ...rest)
        : ts.createSourceFile(name, text, language);
    };
    const files = [...probes.keys()];
    const program = ts.createProgram({ rootNames: files, options, host });
    expect(holdersByType(program, files)).toEqual(files.slice(0, held.length));
  }, PROGRAM_TIMEOUT_MS);
});
