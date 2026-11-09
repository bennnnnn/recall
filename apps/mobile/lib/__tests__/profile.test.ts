import {
  capitalisedName,
  getDisplayName,
  getInitials,
  sanitizeDisplayName,
} from "@/lib/profile";

describe("profile helpers", () => {
  it("sanitizeDisplayName collapses whitespace and enforces length", () => {
    expect(sanitizeDisplayName("  Ada   Lovelace  ")).toBe("Ada Lovelace");
    expect(sanitizeDisplayName("   ")).toBeNull();
    expect(sanitizeDisplayName("x".repeat(81))).toBeNull();
  });

  it("getDisplayName falls back when empty", () => {
    expect(getDisplayName("Ada", "You", "en")).toBe("Ada");
    expect(getDisplayName("  ", "You", "en")).toBe("You");
  });

  // Settings showed "bini" while Home greeted "Bini".
  it("getDisplayName capitalises the first letter as Home does, the rest as stored", () => {
    expect(getDisplayName("  bini lee ", "You", "en")).toBe("Bini lee");
    expect(getDisplayName("deAndre", "You", "en")).toBe("DeAndre");
  });

  // A Turkish "i" is capitalised "İ" in Turkish, "I" elsewhere.
  it("capitalises in the app's language", () => {
    expect(capitalisedName("irem", "tr")).toBe("İrem");
    expect(capitalisedName("irem", "en")).toBe("Irem");
    expect(getInitials("irem ışık", "tr")).toBe("İI");
  });

  it("getInitials uses up to two words", () => {
    expect(getInitials("Ada Lovelace", "en")).toBe("AL");
    expect(getInitials("Cher", "en")).toBe("C");
    expect(getInitials(null, "en")).toBe("?");
  });
});
