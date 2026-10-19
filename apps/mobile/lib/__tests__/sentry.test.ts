import type { ErrorEvent } from "@sentry/react-native";

import { redactSecrets, scrubBreadcrumb, scrubSentryEvent } from "@/lib/sentry";

jest.mock("@sentry/react-native", () => ({
  init: jest.fn(),
  captureException: jest.fn(),
}));

const JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.sig_part_here";

describe("mobile Sentry scrubbing (O10.1)", () => {
  it("drops request bodies, query strings, cookies, auth headers, extras and user fields", () => {
    const event = {
      request: {
        url: "https://api.example.com/chats/1/messages?token=abc",
        query_string: "token=abc",
        data: '{"content":"my private question"}',
        cookies: { session: "s" },
        headers: { Authorization: `Bearer ${JWT}`, Accept: "application/json" },
      },
      extra: { prompt: "my private question" },
      user: { id: "u1", email: "a@b.c", ip_address: "1.2.3.4" },
      exception: { values: [{ type: "Error", value: `Request failed with Bearer ${JWT}` }] },
      breadcrumbs: [
        { category: "console", message: "draft: my private question" },
        {
          category: "fetch",
          data: { method: "POST", url: "https://api.example.com/x?y=1", status_code: 500, body: "text" },
        },
        { category: "navigation", data: { from: "/", to: "/memory" } },
      ],
    } as unknown as ErrorEvent;

    const scrubbed = scrubSentryEvent(event);
    const text = JSON.stringify(scrubbed);

    expect(text).not.toContain("my private question");
    expect(text).not.toContain(JWT);
    expect(text).not.toContain("token=abc");
    expect(text).not.toContain("a@b.c");
    expect(scrubbed?.request?.headers?.Authorization).toBe("[REDACTED]");
    expect(scrubbed?.request?.url).toBe("https://api.example.com/chats/1/messages");
    expect(scrubbed?.user).toEqual({ id: "u1" });
    expect(scrubbed?.breadcrumbs).toEqual([
      { category: "fetch", data: { method: "POST", url: "https://api.example.com/x", status_code: 500 } },
      { category: "navigation", data: { from: "/", to: "/memory" } },
    ]);
  });

  it("redacts tokens and Live Talk secrets, and bounds a long error text", () => {
    expect(redactSecrets("key ek_abcdefghijkl and sk_live_123456789")).toBe(
      "key [REDACTED] and [REDACTED]",
    );
    expect(redactSecrets("x".repeat(400))).toHaveLength(301);
  });

  it("drops console breadcrumbs before they are recorded", () => {
    expect(scrubBreadcrumb({ category: "console", message: "hello" })).toBeNull();
  });
});

describe("error-boundary capture", () => {
  const originalDsn = process.env.EXPO_PUBLIC_SENTRY_DSN;
  afterEach(() => {
    process.env.EXPO_PUBLIC_SENTRY_DSN = originalDsn;
    jest.resetModules();
  });

  function freshSentry() {
    let mod!: typeof import("@/lib/sentry");
    let sdk!: { init: jest.Mock; captureException: jest.Mock };
    jest.isolateModules(() => {
      mod = jest.requireActual("@/lib/sentry");
      sdk = jest.requireMock("@sentry/react-native");
    });
    sdk.init.mockClear();
    sdk.captureException.mockClear();
    return { mod, sdk };
  }

  it("reports nothing when Sentry is not configured", () => {
    delete process.env.EXPO_PUBLIC_SENTRY_DSN;
    const { mod, sdk } = freshSentry();
    mod.initMobileSentry();
    mod.reportBoundaryError("markdown", new Error("render failed"), "in MarkdownContent");
    expect(sdk.init).not.toHaveBeenCalled();
    expect(sdk.captureException).not.toHaveBeenCalled();
  });

  it("captures a boundary crash with its boundary and component stack once configured", () => {
    (globalThis as unknown as { __DEV__: boolean }).__DEV__ = false;
    process.env.EXPO_PUBLIC_SENTRY_DSN = "https://key@sentry.example.com/1";
    const { mod, sdk } = freshSentry();
    mod.initMobileSentry();
    expect(sdk.init).toHaveBeenCalledWith(
      expect.objectContaining({ sendDefaultPii: false, beforeSend: expect.any(Function) }),
    );
    const error = new Error("render failed");
    mod.reportBoundaryError("message_row", error, "\n    in MessageBubble");
    expect(sdk.captureException).toHaveBeenCalledWith(error, {
      tags: { boundary: "message_row" },
      contexts: { react: { componentStack: "\n    in MessageBubble" } },
    });
  });
});
