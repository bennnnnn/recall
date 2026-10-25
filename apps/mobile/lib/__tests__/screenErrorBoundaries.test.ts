/**
 * Structural guard: a screen that throws while it renders shows its own error
 * view (`components/ScreenErrorBoundary.tsx`), so the rest of the app keeps
 * working, and the crash is reported. Without the export, Expo Router sends
 * the error to the root boundary, which replaces the whole app and reports
 * nothing. A new screen route gets one unless it is listed here with a reason.
 */

import { appFiles, readSource, relative, ROOT } from "@/lib/__tests__/support/sourceFiles";

const EXPORT =
  'export { ScreenErrorBoundary as ErrorBoundary } from "@/components/ScreenErrorBoundary";';

/** Routes that still fall to the root's boundary, and why. */
const WITHOUT_OWN_BOUNDARY = new Map([
  ["app/index.tsx", "the chat: each message and each block in it has its own boundary"],
  ["app/login.tsx", "the sign-in flow, before any account screen"],
  ["app/onboarding.tsx", "the sign-in flow, before any account screen"],
  ["app/consent.tsx", "the sign-in flow, before any account screen"],
  ["app/+not-found.tsx", "draws only a link home"],
]);

describe("screen routes", () => {
  const routes = appFiles()
    .map(relative)
    .filter((path) => path.startsWith("app/") && !/\/_layout\.tsx$/.test(path));

  it("finds the route files", () => {
    expect(routes).toEqual(expect.arrayContaining(["app/todos.tsx", "app/settings/profile.tsx"]));
  });

  it("each export their own error boundary", () => {
    const missing = routes.filter(
      (path) => !WITHOUT_OWN_BOUNDARY.has(path) && !readSource(`${ROOT}/${path}`).includes(EXPORT),
    );
    expect(missing).toEqual([]);
  });

  it("lists only routes that exist", () => {
    expect([...WITHOUT_OWN_BOUNDARY.keys()].filter((path) => !routes.includes(path))).toEqual([]);
  });
});
