import { toSubscript, toSuperscript } from "@/lib/unicodeSupSub";

describe("toSuperscript", () => {
  it("maps digits and common letters to Unicode superscripts", () => {
    expect(toSuperscript("2")).toBe("²");
    expect(toSuperscript("x")).toBe("ˣ");
    expect(toSuperscript("n")).toBe("ⁿ");
    expect(toSuperscript("10")).toBe("¹⁰");
  });

  it("maps +/-/= and parens", () => {
    expect(toSuperscript("+")).toBe("⁺");
    expect(toSuperscript("-")).toBe("⁻");
    expect(toSuperscript("(2)")).toBe("⁽²⁾");
  });

  it("returns null when any char lacks a Unicode superscript", () => {
    // q, C, comma have no Unicode superscript.
    expect(toSuperscript("q")).toBeNull();
    expect(toSuperscript("C")).toBeNull();
    expect(toSuperscript("2,3")).toBeNull();
  });

  it("returns null for empty input", () => {
    expect(toSuperscript("")).toBeNull();
  });
});

describe("toSubscript", () => {
  it("maps digits and common letters to Unicode subscripts", () => {
    expect(toSubscript("2")).toBe("₂");
    expect(toSubscript("x")).toBe("ₓ");
    expect(toSubscript("10")).toBe("₁₀");
  });

  it("returns null when any char lacks a Unicode subscript", () => {
    // b, z, comma have no Unicode subscript.
    expect(toSubscript("b")).toBeNull();
    expect(toSubscript("z")).toBeNull();
    expect(toSubscript("2,3")).toBeNull();
  });
});
