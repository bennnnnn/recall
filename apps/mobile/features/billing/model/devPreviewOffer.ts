import type { PlanOffer } from "@/features/billing/model/purchases";

/**
 * Example prices for a development build, which has no store: so the plans page can be seen
 * as a release shows it (the period switch's saving, the price line, the trial, the payment
 * dates). The page says they are examples; a release reads the store's own and never these.
 */
export const DEV_PREVIEW_OFFER: PlanOffer = {
  packages: {
    monthly: {
      plan: "pro",
      period: "monthly",
      priceString: "$7.99",
      price: 7.99,
      productId: "dev_preview_monthly",
      native: {} as never,
      trial: { count: 3, unit: "day", priceString: "$0.00" },
    },
    yearly: {
      plan: "pro",
      period: "yearly",
      priceString: "$59.99",
      price: 59.99,
      pricePerMonth: "$5.00",
      productId: "dev_preview_yearly",
      native: {} as never,
      trial: { count: 3, unit: "day", priceString: "$0.00" },
    },
  },
  unavailable: false,
};
