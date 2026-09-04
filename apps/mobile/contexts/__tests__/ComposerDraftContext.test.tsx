import React from "react";
import { Pressable, Text } from "react-native";
import { act, fireEvent, render } from "@testing-library/react-native";

import {
  ComposerDraftProvider,
  useComposerDraftApi,
  useComposerDraftValueOptional,
} from "@/contexts/ComposerDraftContext";

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
});
