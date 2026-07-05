import { createStaticOnlyNavigationGuard } from "@/lib/staticOnlyNavigationGuard";

describe("createStaticOnlyNavigationGuard", () => {
  it("allows exactly one navigation, then denies the rest", () => {
    const guard = createStaticOnlyNavigationGuard();
    expect(guard.shouldAllow()).toBe(true);
    expect(guard.shouldAllow()).toBe(false);
    expect(guard.shouldAllow()).toBe(false);
  });

  it("denies a link/window.location navigation attempted after the initial load", () => {
    // Simulates the sandbox WebView loading self-contained HTML, then the
    // model/user HTML trying to navigate the WebView itself to another origin.
    const guard = createStaticOnlyNavigationGuard();
    const initialLoad = guard.shouldAllow();
    const linkClickToExternalSite = guard.shouldAllow();

    expect(initialLoad).toBe(true);
    expect(linkClickToExternalSite).toBe(false);
  });

  it("re-arms the one allowed load after reset (new content)", () => {
    const guard = createStaticOnlyNavigationGuard();
    guard.shouldAllow();
    expect(guard.shouldAllow()).toBe(false);

    guard.reset();

    expect(guard.shouldAllow()).toBe(true);
    expect(guard.shouldAllow()).toBe(false);
  });
});
