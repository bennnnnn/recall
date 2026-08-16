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

function ApiProbe({ renders }: { renders: { current: number } }) {
  renders.current += 1;
  const { setInput } = useComposerDraftApi();
  return (
    <Pressable testID="set" onPress={() => setInput("hello")}>
      <Text>set</Text>
    </Pressable>
  );
}

describe("ComposerDraftContext", () => {
  it("updates the value subscriber without re-rendering the api subscriber", async () => {
    const renders = { current: 0 };
    const view = await act(async () =>
      render(
        <ComposerDraftProvider>
          <ValueProbe />
          <ApiProbe renders={renders} />
        </ComposerDraftProvider>,
      ),
    );
    const afterMount = renders.current;
    expect(view.getByTestId("draft").props.children).toBe("");

    await act(async () => {
      fireEvent.press(view.getByTestId("set"));
    });

    expect(view.getByTestId("draft").props.children).toBe("hello");
    expect(renders.current).toBe(afterMount);
  });
});
