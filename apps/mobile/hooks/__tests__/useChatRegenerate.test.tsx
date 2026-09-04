import React from "react";
import { Text } from "react-native";
import { act, render } from "@testing-library/react-native";

import { useChatRegenerate } from "@/hooks/useChatRegenerate";
import type { Message, User } from "@/lib/api";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

jest.mock("@/lib/resolveClientGeoForQuery", () => ({
  resolveClientGeoForQuery: jest.fn(async () => ({ ok: true, clientGeo: null })),
}));

import { resolveClientGeoForQuery } from "@/lib/resolveClientGeoForQuery";

const resolveGeo = resolveClientGeoForQuery as jest.Mock;

const user: User = {
  id: "u1",
  email: "test@recall.local",
  name: null,
  plan: "free",
  created_at: "2026-01-01T00:00:00Z",
  location_enabled: false,
} as User;

function msg(role: "user" | "assistant", content: string, id: string): Message {
  return {
    id,
    role,
    content,
    model: role === "assistant" ? "free-chat" : null,
    created_at: "2026-01-01T00:00:00Z",
  } as Message;
}

type Regenerate = (model: string) => Promise<void>;

let currentRegenerate: Regenerate;
let currentRegenerating = false;

function Probe({
  messages,
  regenerateResponse,
  regenerateImage,
  beginRegenerateUi,
  cancelRegenerateUi,
}: {
  messages: Message[];
  regenerateResponse: jest.Mock;
  regenerateImage?: jest.Mock;
  beginRegenerateUi?: jest.Mock;
  cancelRegenerateUi?: jest.Mock;
}) {
  const result = useChatRegenerate({
    token: "tok",
    messages,
    user,
    updateUser: jest.fn(),
    regenerateResponse,
    beginRegenerateUi,
    cancelRegenerateUi,
    regenerateImage,
  });
  React.useLayoutEffect(() => {
    currentRegenerate = result.regenerate;
    currentRegenerating = result.regenerating;
  }, [result]);
  return <Text>{result.regenerating ? "busy" : "idle"}</Text>;
}

describe("useChatRegenerate", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resolveGeo.mockResolvedValue({ ok: true, clientGeo: null });
  });

  it("does not dispatch a regeneration stopped while location preparation is pending", async () => {
    let finish!: (value: { ok: boolean; clientGeo: null }) => void;
    resolveGeo.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
    let active = true;
    const regenerateResponse = jest.fn();
    const cancelRegenerateUi = jest.fn();
    await render(<Probe
      messages={[msg("user", "question", "u1"), msg("assistant", "answer", "a1")]}
      regenerateResponse={regenerateResponse}
      beginRegenerateUi={jest.fn(() => () => active)}
      cancelRegenerateUi={cancelRegenerateUi}
    />);
    let pending!: Promise<void>;
    await act(async () => { pending = currentRegenerate("free-chat"); });
    active = false;
    await act(async () => { finish({ ok: true, clientGeo: null }); await pending; });
    expect(regenerateResponse).not.toHaveBeenCalled();
    expect(cancelRegenerateUi).not.toHaveBeenCalled();
  });

  it("routes to regenerateImage when last assistant is an image-only reply", async () => {
    const messages: Message[] = [
      msg("user", "Generate image: a cat", "u1"),
      msg("assistant", "[Image: cat.png]", "a1"),
    ];
    const regenerateResponse = jest.fn();
    const regenerateImage = jest.fn();

    await act(async () => {
      render(
        <Probe
          messages={messages}
          regenerateResponse={regenerateResponse}
          regenerateImage={regenerateImage}
        />,
      );
    });

    await act(async () => {
      await currentRegenerate("free-chat");
    });

    expect(regenerateImage).toHaveBeenCalledWith("Generate image: a cat");
    expect(regenerateResponse).not.toHaveBeenCalled();
  });

  it("falls back to regenerateResponse for normal text replies", async () => {
    const messages: Message[] = [
      msg("user", "Hello", "u1"),
      msg("assistant", "Hi there!", "a1"),
    ];
    const regenerateResponse = jest.fn();
    const regenerateImage = jest.fn();

    await act(async () => {
      render(
        <Probe
          messages={messages}
          regenerateResponse={regenerateResponse}
          regenerateImage={regenerateImage}
        />,
      );
    });

    await act(async () => {
      await currentRegenerate("free-chat");
    });

    expect(regenerateResponse).toHaveBeenCalled();
    expect(regenerateImage).not.toHaveBeenCalled();
  });

  it("retries a user-only failed turn without adding another user message", async () => {
    const messages = [msg("user", "My first question", "u1")];
    const regenerateResponse = jest.fn();

    await act(async () => {
      render(<Probe messages={messages} regenerateResponse={regenerateResponse} />);
    });

    await act(async () => {
      await currentRegenerate("free-chat");
    });

    expect(regenerateResponse).toHaveBeenCalledWith("free-chat", null);
    expect(messages).toHaveLength(1);
    expect(messages[0]).toMatchObject({ role: "user", content: "My first question" });
  });

  it("does not route to image path when regenerateImage is not provided", async () => {
    const messages: Message[] = [
      msg("user", "Generate image: a cat", "u1"),
      msg("assistant", "[Image: cat.png]", "a1"),
    ];
    const regenerateResponse = jest.fn();

    await act(async () => {
      render(<Probe messages={messages} regenerateResponse={regenerateResponse} />);
    });

    await act(async () => {
      await currentRegenerate("free-chat");
    });

    expect(regenerateResponse).toHaveBeenCalled();
  });

  it("blocks duplicate regeneration while the first request is pending", async () => {
    let finish: (() => void) | undefined;
    const regenerateResponse = jest.fn(
      () =>
        new Promise<void>((resolve) => {
          finish = resolve;
        }),
    );
    const messages = [msg("user", "Hello", "u1"), msg("assistant", "Hi", "a1")];
    await act(async () => {
      render(<Probe messages={messages} regenerateResponse={regenerateResponse} />);
    });

    let first: Promise<void> = Promise.resolve();
    await act(async () => {
      first = currentRegenerate("free-chat");
      await Promise.resolve();
      await currentRegenerate("free-chat");
    });

    expect(regenerateResponse).toHaveBeenCalledTimes(1);
    expect(currentRegenerating).toBe(true);

    await act(async () => {
      finish?.();
      await first;
    });
    expect(currentRegenerating).toBe(false);
  });

  it("shows the typing placeholder before geo resolves", async () => {
    let finishGeo: (value: { ok: true; clientGeo: null }) => void = () => undefined;
    resolveGeo.mockReturnValue(
      new Promise((resolve) => {
        finishGeo = resolve;
      }),
    );
    const beginRegenerateUi = jest.fn();
    const regenerateResponse = jest.fn();
    const messages = [msg("user", "Hello", "u1"), msg("assistant", "Hi", "a1")];
    await act(async () => {
      render(
        <Probe
          messages={messages}
          regenerateResponse={regenerateResponse}
          beginRegenerateUi={beginRegenerateUi}
        />,
      );
    });

    let regenPromise: Promise<void> = Promise.resolve();
    await act(async () => {
      regenPromise = currentRegenerate("free-chat");
      await Promise.resolve();
    });

    expect(beginRegenerateUi).toHaveBeenCalledTimes(1);
    expect(regenerateResponse).not.toHaveBeenCalled();

    await act(async () => {
      finishGeo({ ok: true, clientGeo: null });
      await regenPromise;
    });
    expect(regenerateResponse).toHaveBeenCalledWith("free-chat", null);
  });

  it("restores the prior assistant when geo is cancelled", async () => {
    resolveGeo.mockResolvedValue({ ok: false });
    const beginRegenerateUi = jest.fn();
    const cancelRegenerateUi = jest.fn();
    const regenerateResponse = jest.fn();
    const messages = [msg("user", "Hello", "u1"), msg("assistant", "Hi", "a1")];
    await act(async () => {
      render(
        <Probe
          messages={messages}
          regenerateResponse={regenerateResponse}
          beginRegenerateUi={beginRegenerateUi}
          cancelRegenerateUi={cancelRegenerateUi}
        />,
      );
    });

    await act(async () => {
      await currentRegenerate("free-chat");
    });

    expect(beginRegenerateUi).toHaveBeenCalledTimes(1);
    expect(cancelRegenerateUi).toHaveBeenCalledTimes(1);
    expect(regenerateResponse).not.toHaveBeenCalled();
  });
});
