import { MODEL_CATALOG_FALLBACK } from "@/lib/modelCatalogFallback";

describe("model catalog fallback", () => {
  it.each([
    ["glm-5.3", 1.4, 4.4, "smart"],
    ["qwen-3.8-max", 2, 6, "smart"],
    ["minimax-m3", 0.23, 0.96, "standard"],
    ["kimi-k3", 2.6, 13, "smart"],
  ] as const)(
    "includes %s with matching pricing and tier",
    (id, inputPrice, outputPrice, tier) => {
      const model = MODEL_CATALOG_FALLBACK.find((entry) => entry.id === id);

      expect(model).toMatchObject({
        id,
        tier,
        plan_access: "pro",
        available: true,
        input_price_per_m: inputPrice,
        output_price_per_m: outputPrice,
      });
    },
  );
});
