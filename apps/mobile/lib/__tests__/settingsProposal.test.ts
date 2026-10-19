import {
  isMemoryProposal,
  parseSettingsProposals,
  stripSettingsProposalFences,
} from "@/lib/settingsProposal";

describe("settingsProposal", () => {
  it("parses and strips settings_proposal fences", () => {
    const content = [
      "I can switch that for you: Appearance → Dark.",
      "```settings_proposal",
      '{"proposal_id":"abc","changes":[{"field":"appearance","value":"dark","label":"Dark"}]}',
      "```",
    ].join("\n");

    const proposals = parseSettingsProposals(content);
    expect(proposals).toHaveLength(1);
    expect(proposals[0]?.proposal_id).toBe("abc");
    expect(proposals[0]?.changes[0]?.value).toBe("dark");
    expect(stripSettingsProposalFences(content)).toBe(
      "I can switch that for you: Appearance → Dark.",
    );
  });

  it("reads a memory reset card the chat proposes", () => {
    const content = [
      "I can delete everything Recall has saved about you. This can't be undone.",
      "```settings_proposal",
      '{"proposal_id":"m1","changes":[{"field":"memory","value":"clear","label":"Delete everything saved"}]}',
      "```",
    ].join("\n");

    const [proposal] = parseSettingsProposals(content);
    expect(proposal?.changes[0]).toEqual({
      field: "memory",
      value: "clear",
      label: "Delete everything saved",
    });
    expect(proposal && isMemoryProposal(proposal)).toBe(true);
  });

  it("drops fences without a proposal id", () => {
    const content = '```settings_proposal\n{"changes":[]}\n```';
    expect(parseSettingsProposals(content)).toEqual([]);
  });
});
