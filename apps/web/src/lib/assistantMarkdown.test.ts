import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { prepareAssistantMarkdown } from "./assistantMarkdown.ts";

function chemicalStructureCount(markdown: string): number {
  return markdown.split("Chemical structure").length - 1;
}

describe("prepareAssistantMarkdown molecule pair", () => {
  it("does not emit a second Chemical structure label for paired molecule3d", () => {
    const markdown =
      "```smiles\nCCO\n```\n\n```molecule3d\nEthanol\n     RDKit          3D\n\n  3  2  0  0  0  0  0  0  0  0999 V2000\nM  END\n```";
    const out = prepareAssistantMarkdown(markdown);
    assert.equal(chemicalStructureCount(out), 1);
    assert.equal(out.includes("V2000"), false);
    assert.equal(out.includes("```"), false);
  });

  it("keeps a Chemical structure label for standalone molecule3d", () => {
    const out = prepareAssistantMarkdown(
      "```molecule3d\nEthanol\n     RDKit          3D\n\n  3  2  0  0  0  0  0  0  0  0999 V2000\nM  END\n```",
    );
    assert.equal(chemicalStructureCount(out), 1);
  });

  it("skips a later molecule3d after smiles even when a heading sits between", () => {
    const markdown =
      "```smiles\nCCO\n```\n\n## 3D Structure\n\n```molecule3d\nEthanol\n     RDKit          3D\n\n  3  2  0  0  0  0  0  0  0  0999 V2000\nM  END\n```";
    const out = prepareAssistantMarkdown(markdown);
    assert.equal(chemicalStructureCount(out), 1);
    assert.equal(out.includes("V2000"), false);
  });
});
