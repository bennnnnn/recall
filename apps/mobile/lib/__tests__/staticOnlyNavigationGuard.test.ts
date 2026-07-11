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

  it("reset before any navigation request is a no-op", () => {
    const guard = createStaticOnlyNavigationGuard();
    guard.reset();

    expect(guard.shouldAllow()).toBe(true);
    expect(guard.shouldAllow()).toBe(false);
  });

  it("supports repeated reset/consume cycles, always re-arming exactly one load", () => {
    const guard = createStaticOnlyNavigationGuard();

    for (let i = 0; i < 5; i += 1) {
      guard.reset();
      expect(guard.shouldAllow()).toBe(true);
      expect(guard.shouldAllow()).toBe(false);
      expect(guard.shouldAllow()).toBe(false);
    }
  });

  it("calling reset multiple times in a row does not grant extra navigations", () => {
    const guard = createStaticOnlyNavigationGuard();
    guard.shouldAllow();

    guard.reset();
    guard.reset();
    guard.reset();

    expect(guard.shouldAllow()).toBe(true);
    expect(guard.shouldAllow()).toBe(false);
  });

  it("gives each guard instance independent state", () => {
    const guardA = createStaticOnlyNavigationGuard();
    const guardB = createStaticOnlyNavigationGuard();

    expect(guardA.shouldAllow()).toBe(true);
    expect(guardA.shouldAllow()).toBe(false);

    // guardB is unaffected by guardA having consumed its one allowed load.
    expect(guardB.shouldAllow()).toBe(true);
    expect(guardB.shouldAllow()).toBe(false);
  });
});
