import type { ModelInfo } from "@/lib/api";

/** The model list before the first /models response on a fresh install (no
 * cached catalog yet): the one model the composer needs to send. The server
 * owns the catalog, its prices and its quota multipliers; the phone keeps no
 * copy of them, so this row names the product, not the model behind the alias
 * (the server can point `free-chat` at another model without a phone update). */
export const MODEL_CATALOG_FALLBACK: ModelInfo[] = [
  {
    id: "free-chat",
    label: "Recall",
    tier: "fast",
    plan_access: "free",
    description: "Everyday chat.",
    available: true,
  },
];
