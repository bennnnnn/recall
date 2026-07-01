import {
  extractPlacesFromMarkdownList,
  googleMapsSearchUrl,
  isGenericSearchUrl,
  parsePlacesFence,
  parsePlacesJson,
  repairBrokenMarkdownLinks,
  resolvePlaceLinkUrl,
  resolvePlaces,
  stripPlacesContent,
  stripPlacesFence,
} from "@/lib/placesList";

describe("placesList", () => {
  it("parses places fence", () => {
    const content = `Here are salons:

\`\`\`places
[{"name":"CODE Salon","url":"https://example.com/code","note":"4.7 stars","price":"$$"}]
\`\`\``;
    expect(parsePlacesFence(content)).toEqual([
      {
        name: "CODE Salon",
        url: "https://example.com/code",
        note: "4.7 stars",
        price: "$$",
      },
    ]);
    expect(stripPlacesFence(content)).toBe("Here are salons:");
  });

  it("repairs broken markdown links with dollar delimiters", () => {
    const broken =
      "1. [CODE Salon]$https://www.yelp.com/biz/code-salon$ — Top-rated";
    expect(repairBrokenMarkdownLinks(broken)).toBe(
      "1. [CODE Salon](https://www.yelp.com/biz/code-salon) — Top-rated",
    );
  });

  it("parses minimal rows", () => {
    expect(parsePlacesJson('[{"name":"A","address":"1 Main St"}]')).toEqual([
      {
        name: "A",
        url: "https://www.google.com/maps/search/?api=1&query=A%2C%201%20Main%20St",
        address: "1 Main St",
      },
    ]);
  });

  it("resolves to google maps using address", () => {
    const url = resolvePlaceLinkUrl({
      name: "CODE Salon",
      url: "https://www.yelp.com/search?find_desc=Hair+Salons",
      address: "123 Market St, San Francisco",
    });
    expect(url).toContain("google.com/maps/search");
    expect(url).toContain("123%20Market%20St");
    expect(isGenericSearchUrl("https://www.yelp.com/search?q=x")).toBe(true);
  });

  it("preserves direct venue URLs", () => {
    expect(
      resolvePlaceLinkUrl({
        name: "Benu",
        url: "https://www.yelp.com/biz/benu-san-francisco",
        address: "22 Hawthorne St",
      }),
    ).toBe("https://www.yelp.com/biz/benu-san-francisco");
  });

  it("builds maps url from name when address missing", () => {
    expect(googleMapsSearchUrl("CODE Salon")).toContain("CODE%20Salon");
  });

  it("extracts legacy markdown restaurant lists into places", () => {
    const content = `Here are top spots:

1. **Benu** – 3-Michelin stars, modern Asian fusion ($$$)
2. **Atelier Crenn** – Poetic, French-inspired ($$$)

Want a reservation?`;

    const places = extractPlacesFromMarkdownList(content);
    expect(places).toHaveLength(2);
    expect(places[0].name).toBe("Benu");
    expect(places[0].price).toBe("$$$");
    expect(places[0].url).toContain("google.com/maps");
  });

  it("resolvePlaces ignores plain numbered lists (math, steps, etc.)", () => {
    const math = `Area: 12 cm²

1. **Base (b):**
   6 cm (the bottom side)
2. **Height (h):**
   4 cm (the vertical side)
3. **Hypotenuse (c):**
   ≈ 7.21 cm`;

    expect(resolvePlaces(math)).toEqual([]);
  });

  it("resolvePlaces reads mis-tagged json venue arrays", () => {
    const content = `Here are gas stations:

\`\`\`json
[{"name":"Shell","url":"https://maps.google.com/?q=shell","address":"123 Market St","price":"$"}]
\`\`\``;
    expect(resolvePlaces(content)).toEqual([
      expect.objectContaining({ name: "Shell", address: "123 Market St" }),
    ]);
    const places = resolvePlaces(content);
    expect(stripPlacesContent(content, places)).not.toContain("```json");
  });

  it("resolvePlaces only reads explicit places fences", () => {
    const content = `Intro
1. **Old List Item** – should ignore
\`\`\`places
[{"name":"From Fence","url":"https://example.com","address":"1 Main"}]
\`\`\``;
    expect(resolvePlaces(content)).toEqual([
      expect.objectContaining({ name: "From Fence" }),
    ]);
  });

  it("stripPlacesContent removes only the places fence", () => {
    const content = `Here are picks:

1. **Benu** – fusion ($$)

\`\`\`places
[{"name":"Benu","url":"https://x.com","address":"SF"}]
\`\`\``;
    const places = resolvePlaces(content);
    const stripped = stripPlacesContent(content, places);
    expect(stripped).toContain("Here are picks");
    expect(stripped).toContain("**Benu**");
    expect(stripped).not.toContain("```places");
  });
});
