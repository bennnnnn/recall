import React from "react";
import { Pressable, Text } from "react-native";
import { act, fireEvent, render } from "@testing-library/react-native";

import {
  ComposerDraftProvider,
  useComposerDraftApi,
  useComposerDraftValueOptional,
} from "@/contexts/ComposerDraftContext";
import { resetComposerDraftsForAccount } from "@/lib/chat/composerDraftReset";

function ValueProbe() {
  const draft = useComposerDraftValueOptional();
  return <Text testID="draft">{draft?.input ?? ""}</Text>;
}

function ApiProbe({ onRender }: { onRender: () => void }) {
  React.useLayoutEffect(onRender);
  const { setInput } = useComposerDraftApi();
  return (
    <Pressable testID="set" onPress={() => setInput("hello")}>
      <Text>set</Text>
    </Pressable>
  );
}

describe("ComposerDraftContext", () => {
  it("updates the value subscriber without re-rendering the api subscriber", async () => {
    const onRender = jest.fn();
    const view = await act(async () =>
      render(
        <ComposerDraftProvider>
          <ValueProbe />
          <ApiProbe onRender={onRender} />
        </ComposerDraftProvider>,
      ),
    );
    const afterMount = onRender.mock.calls.length;
    expect(view.getByTestId("draft").props.children).toBe("");

    await act(async () => {
      fireEvent.press(view.getByTestId("set"));
    });

    expect(view.getByTestId("draft").props.children).toBe("hello");
    expect(onRender).toHaveBeenCalledTimes(afterMount);
  });

  it("restores a saved draft when switching back to a thread", async () => {
    function SwitchProbe() {
      const { setInput, switchThread } = useComposerDraftApi();
      return (
        <>
          <Pressable testID="type-new" onPress={() => setInput("from new")}>
            <Text>type</Text>
          </Pressable>
          <Pressable testID="to-b" onPress={() => switchThread("b")}>
            <Text>b</Text>
          </Pressable>
          <Pressable testID="type-b" onPress={() => setInput("from b")}>
            <Text>type b</Text>
          </Pressable>
          <Pressable testID="to-new" onPress={() => switchThread("new")}>
            <Text>new</Text>
          </Pressable>
        </>
      );
    }

    const view = await act(async () =>
      render(
        <ComposerDraftProvider>
          <ValueProbe />
          <SwitchProbe />
        </ComposerDraftProvider>,
      ),
    );

    await act(async () => {
      fireEvent.press(view.getByTestId("type-new"));
    });
    expect(view.getByTestId("draft").props.children).toBe("from new");

    await act(async () => {
      fireEvent.press(view.getByTestId("to-b"));
    });
    expect(view.getByTestId("draft").props.children).toBe("");

    await act(async () => {
      fireEvent.press(view.getByTestId("type-b"));
    });
    await act(async () => {
      fireEvent.press(view.getByTestId("to-new"));
    });
    expect(view.getByTestId("draft").props.children).toBe("from new");
  });

  it("clears the visible draft and stored threads on session reset", async () => {
    function ResetProbe() {
      const { setInput, switchThread, resetForNewSession } = useComposerDraftApi();
      return (
        <>
          <Pressable testID="type-new" onPress={() => setInput("account A secret")}>
            <Text>type</Text>
          </Pressable>
          <Pressable testID="to-b" onPress={() => switchThread("b")}>
            <Text>b</Text>
          </Pressable>
          <Pressable testID="reset" onPress={() => resetForNewSession()}>
            <Text>reset</Text>
          </Pressable>
          <Pressable testID="to-new" onPress={() => switchThread("new")}>
            <Text>new</Text>
          </Pressable>
        </>
      );
    }

    const view = await act(async () =>
      render(
        <ComposerDraftProvider>
          <ValueProbe />
          <ResetProbe />
        </ComposerDraftProvider>,
      ),
    );

    await act(async () => {
      fireEvent.press(view.getByTestId("type-new"));
    });
    await act(async () => {
      fireEvent.press(view.getByTestId("to-b"));
    });
    await act(async () => {
      fireEvent.press(view.getByTestId("reset"));
    });
    expect(view.getByTestId("draft").props.children).toBe("");

    await act(async () => {
      fireEvent.press(view.getByTestId("to-new"));
    });
    expect(view.getByTestId("draft").props.children).toBe("");
  });

  it("does not stash the live draft when reset and switchThread run in the same tick", async () => {
    function Probe() {
      const { setInput, switchThread, resetForNewSession } = useComposerDraftApi();
      return (
        <>
          <Pressable testID="type" onPress={() => setInput("account A secret")}>
            <Text>type</Text>
          </Pressable>
          <Pressable
            testID="reset-then-switch"
            onPress={() => {
              resetForNewSession();
              switchThread("chat-b");
            }}
          >
            <Text>reset then switch</Text>
          </Pressable>
          <Pressable testID="to-new" onPress={() => switchThread("new")}>
            <Text>new</Text>
          </Pressable>
        </>
      );
    }

    const view = await act(async () =>
      render(
        <ComposerDraftProvider>
          <ValueProbe />
          <Probe />
        </ComposerDraftProvider>,
      ),
    );

    await act(async () => {
      fireEvent.press(view.getByTestId("type"));
    });
    await act(async () => {
      fireEvent.press(view.getByTestId("reset-then-switch"));
    });
    expect(view.getByTestId("draft").props.children).toBe("");

    await act(async () => {
      fireEvent.press(view.getByTestId("to-new"));
    });
    expect(view.getByTestId("draft").props.children).toBe("");
  });

  it("clears drafts when sign-out broadcasts a reset", async () => {
    const view = await act(async () =>
      render(
        <ComposerDraftProvider>
          <ValueProbe />
          <ApiProbe onRender={() => undefined} />
        </ComposerDraftProvider>,
      ),
    );
    await act(async () => {
      fireEvent.press(view.getByTestId("set"));
    });
    expect(view.getByTestId("draft").props.children).toBe("hello");
    await act(async () => {
      resetComposerDraftsForAccount();
    });
    expect(view.getByTestId("draft").props.children).toBe("");
  });
});
