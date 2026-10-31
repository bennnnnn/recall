/**
 * One owner of the chat thread (structure ticket ST-08): the list of messages on screen is
 * React state in `useChat`, and every change to it is a step of the turn reducer — the turn's
 * own frames, or a `thread_edit` another writer sends through `editThread`. Only `useChat`,
 * which holds the setter, and the reducer's command runner may touch the setter, and no other
 * file holds a setter for a list of messages, so a second owner cannot appear under a new name.
 */
import * as ts from "typescript";

declare const __dirname: string;

const ROOT = ts.sys.resolvePath(`${__dirname}/../..`);
const OWNERS = ["features/chat/hooks/useChat.ts", "features/chat/model/chatTurnEffects.ts"];
// The setter by name, a setter for a list of messages under any name, and a second list held
// in React state. (useChat.test.tsx checks the hook hands out no setter under any key.)
const SETTER = /\bsetMessages\b|Dispatch<SetStateAction<(readonly )?Message\[\]>>|useState<(readonly )?Message\[\]>/;

function productionFiles(): string[] {
  return ["app", "components", "contexts", "features", "hooks", "lib", "ui"]
    .flatMap((dir) =>
      ts.sys.readDirectory(`${ROOT}/${dir}`, [".ts", ".tsx"], ["**/__tests__/**", "**/vendor/**"]),
    )
    .filter((file) => !file.endsWith(".d.ts"));
}

describe("the chat thread's owner", () => {
  it("only useChat and the turn's command runner hold the thread's setter", () => {
    const holders = productionFiles()
      .filter((file) => SETTER.test(ts.sys.readFile(file) ?? ""))
      .map((file) => file.slice(ROOT.length + 1))
      .sort();
    expect(holders).toEqual(OWNERS);
  });
});
