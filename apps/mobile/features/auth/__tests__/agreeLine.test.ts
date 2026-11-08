import en from "@/lib/i18n/en.json";

it("says only that continuing agrees to the Terms and Privacy Policy", () => {
  // The user's wording (2026-11-06). A later commit lengthened it without asking; this holds it.
  expect(en["login.agree_line"]).toBe(
    "By continuing, you agree to the <terms>Terms</terms> and <privacy>Privacy Policy</privacy>.",
  );
});
