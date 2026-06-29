import {
  parseCalendarProposals,
  stripCalendarProposalFences,
} from "@/lib/calendarProposal";

describe("calendarProposal", () => {
  it("parses and strips calendar_proposal fences", () => {
    const content = [
      "I'll add this for you:",
      "```calendar_proposal",
      '{"title":"Team sync","start_at":"2026-06-28T15:00:00-07:00","end_at":"2026-06-28T16:00:00-07:00","proposal_id":"abc"}',
      "```",
    ].join("\n");

    const proposals = parseCalendarProposals(content);
    expect(proposals).toHaveLength(1);
    expect(proposals[0]?.title).toBe("Team sync");
    expect(proposals[0]?.proposal_id).toBe("abc");
    expect(stripCalendarProposalFences(content)).toBe("I'll add this for you:");
  });
});
