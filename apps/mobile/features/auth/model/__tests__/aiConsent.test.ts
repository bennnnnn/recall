import {
  aiConsentRedirect,
  needsAiDataConsent,
} from "@/features/auth/model/aiConsent";
import en from "@/lib/i18n/en.json";

describe("needsAiDataConsent", () => {
  it("asks a signed-in account the server says has not agreed", () => {
    expect(needsAiDataConsent({ ai_data_consent_at: null })).toBe(true);
  });

  it("lets an account that agreed through", () => {
    expect(needsAiDataConsent({ ai_data_consent_at: "2026-10-19T12:00:00Z" })).toBe(false);
  });

  it("lets an unknown answer through (older server or an old cold-start cache)", () => {
    expect(needsAiDataConsent({})).toBe(false);
    expect(needsAiDataConsent({ ai_data_consent_at: undefined })).toBe(false);
  });

  it("never asks while signed out", () => {
    expect(needsAiDataConsent(null)).toBe(false);
    expect(needsAiDataConsent(undefined)).toBe(false);
  });
});

describe("aiConsentRedirect", () => {
  const notYet = { ai_data_consent_at: null };

  it.each(["/", "/todos", "/settings/data-controls", "/memory", "/gallery"])(
    "sends an account that has not agreed from %s to the consent screen",
    (pathname) => {
      expect(aiConsentRedirect(notYet, pathname)).toBe("/consent");
    },
  );

  it.each(["/consent", "/login", "/onboarding"])("leaves %s alone", (pathname) => {
    expect(aiConsentRedirect(notYet, pathname)).toBeNull();
  });

  it("never redirects an account that agreed, an unknown answer or a signed-out user", () => {
    expect(aiConsentRedirect({ ai_data_consent_at: "2026-10-19T12:00:00Z" }, "/")).toBeNull();
    expect(aiConsentRedirect({}, "/")).toBeNull();
    expect(aiConsentRedirect(null, "/")).toBeNull();
  });
});

describe("what the consent says", () => {
  const strings = en as Record<string, string>;

  // One sentence, no list to read through (owner, 2026-11-25); the privacy policy holds the
  // detail. It still names who receives the data (App Store 5.1.2(i)).
  it("names the outside AI services in the screen's one sentence", () => {
    for (const name of ["OpenRouter", "OpenAI"]) {
      expect(strings["onboarding.consent_intro"]).toContain(name);
    }
  });
});
