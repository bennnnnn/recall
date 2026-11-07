import en from "@/lib/i18n/en.json";

it("says at sign-in that chats and voice go to third-party AI providers", () => {
  // The sign-in tap records AI-data consent (features/auth/api.ts), so the line above the
  // buttons must say what is agreed to, not only the Terms and the Privacy Policy.
  expect(en["login.agree_line"]).toMatch(
    /chats and voice are processed by third-party AI providers/,
  );
});
