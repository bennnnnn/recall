/**
 * Structural guard: a screen that throws while it renders shows the shared error
 * view (`components/ScreenErrorBoundary.tsx`), so the rest of the app keeps
 * working, and the crash is reported. Without one, Expo Router sends the error
 * to the root boundary, which replaces the whole app and reports nothing.
 *
 * Routes stay one-line adapters (apps/api architecture tests hold them so), so
 * the boundary comes from the section's stack layout (Settings, Memory: a crash
 * on any of its pages), or from the screen module a one-line route also
 * re-exports it from (`export { default, ErrorBoundary } from "@/…Screen";`).
 * A new screen route gets one unless it is listed here with a reason.
 */
import { appFiles, readSource, relative, ROOT } from "@/lib/__tests__/support/sourceFiles";

const EXPORT =
  'export { ScreenErrorBoundary as ErrorBoundary } from "@/components/ScreenErrorBoundary";';
const ROUTE_WITH_BOUNDARY = /^export \{ default, ErrorBoundary \} from "@\/(.+)";$/;

/** Routes that still fall to the root's boundary, and why. */
const WITHOUT_OWN_BOUNDARY = new Map([
  ["app/index.tsx", "the chat: each message and each block in it has its own boundary"],
  ["app/login.tsx", "the sign-in flow, before any account screen"],
  ["app/onboarding.tsx", "the sign-in flow, before any account screen"],
  ["app/consent.tsx", "the sign-in flow, before any account screen"],
  ["app/+not-found.tsx", "draws only a link home"],
]);

const SOURCES = new Set(appFiles().map(relative));

function exportsBoundary(path: string): boolean {
  return SOURCES.has(path) && readSource(`${ROOT}/${path}`).includes(EXPORT);
}

/** A stack layout between the route and the app root exports the error view. */
function sectionHasBoundary(route: string): boolean {
  const folders = route.split("/").slice(0, -1);
  for (let depth = folders.length; depth > 1; depth -= 1) {
    if (exportsBoundary(`${folders.slice(0, depth).join("/")}/_layout.tsx`)) return true;
  }
  return false;
}

/** The one-line route re-exports the error view its screen module exports. */
function screenHasBoundary(route: string): boolean {
  const match = ROUTE_WITH_BOUNDARY.exec(readSource(`${ROOT}/${route}`).trim());
  return match !== null && exportsBoundary(`${match[1]}.tsx`);
}

describe("screen routes", () => {
  const routes = [...SOURCES]
    .filter((path) => path.startsWith("app/") && !/\/_layout\.tsx$/.test(path));

  it("finds the route files", () => {
    expect(routes).toEqual(expect.arrayContaining(["app/todos.tsx", "app/settings/profile.tsx"]));
  });

  it("each have their own error boundary", () => {
    const missing = routes.filter(
      (path) => !WITHOUT_OWN_BOUNDARY.has(path) && !sectionHasBoundary(path) && !screenHasBoundary(path),
    );
    expect(missing).toEqual([]);
  });

  it("lists only routes that exist", () => {
    expect([...WITHOUT_OWN_BOUNDARY.keys()].filter((path) => !routes.includes(path))).toEqual([]);
  });
});
