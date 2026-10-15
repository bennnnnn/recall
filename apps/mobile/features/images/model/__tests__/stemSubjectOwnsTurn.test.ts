import { stemSubjectOwnsTurn } from "@/features/images/model/stemSubjectOwnsTurn";

const mockImageIntent = jest.fn();
jest.mock("@/lib/api", () => ({
  api: { imageIntent: (...args: unknown[]) => mockImageIntent(...args) },
}));

describe("stemSubjectOwnsTurn", () => {
  beforeEach(() => mockImageIntent.mockReset());

  it("is true when the server names a subject", async () => {
    mockImageIntent.mockResolvedValue({ subject: "chemistry" });
    await expect(stemSubjectOwnsTurn("token", "draw ethanol")).resolves.toBe(true);
    expect(mockImageIntent).toHaveBeenCalledWith("token", "draw ethanol");
  });

  it("is false when the server leaves the turn to a picture", async () => {
    mockImageIntent.mockResolvedValue({ subject: null });
    await expect(stemSubjectOwnsTurn("token", "draw me a cat")).resolves.toBe(false);
  });

  it("keeps the phone's reading when the server cannot answer", async () => {
    mockImageIntent.mockRejectedValue(new Error("Request canceled"));
    await expect(stemSubjectOwnsTurn("token", "draw ethanol")).resolves.toBe(false);
  });

  it("does not ask without a session", async () => {
    await expect(stemSubjectOwnsTurn(null, "draw ethanol")).resolves.toBe(false);
    expect(mockImageIntent).not.toHaveBeenCalled();
  });
});
