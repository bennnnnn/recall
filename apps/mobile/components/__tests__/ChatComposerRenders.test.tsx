import { Dimensions } from "react-native";
import { act, fireEvent, render } from "@testing-library/react-native";

import { ChatComposer } from "@/features/chat/components/ChatComposer";

import { DraftHarness } from "./DraftHarness";

/**
 * How often the whole composer renders for one typed character. A keystroke
 * reaches JS as separate native events: the text, the selection, and the
 * off-screen measure of the draft at the field width.
 */

const mockComposerRenders = jest.fn();

jest.mock("@/features/chat/hooks/useComposerFieldLayout", () => {
  const actual = jest.requireActual("@/features/chat/hooks/useComposerFieldLayout");
  return {
    useComposerFieldLayout: (...args: unknown[]) => {
      mockComposerRenders();
      return actual.useComposerFieldLayout(...args);
    },
  };
});

jest.mock("expo-linear-gradient", () => {
  const { View } = jest.requireActual("react-native") as typeof import("react-native");
  return { LinearGradient: View };
});
jest.mock("@/contexts/AuthContext", () => ({ useAuthToken: () => "t" }));
jest.mock("@/features/speech/components/VoiceComposerWaveform", () => ({
  VoiceComposerWaveform: () => null,
}));
jest.mock("@/features/attachments/components/ComposerAttachmentPreview", () => ({
  ComposerAttachmentPreview: () => null,
}));

// The RN jest preset reports a 2x text size; type at the default.
const presetDimensionsGet = Dimensions.get.bind(Dimensions);
jest
  .spyOn(Dimensions, "get")
  .mockImplementation((dim) => ({ ...presetDimensionsGet(dim), fontScale: 1 }));

const props = {
  visible: true,
  streaming: false,
  pendingAttachment: null,
  onRemoveAttachment: jest.fn(),
  onCloseAttachSheet: jest.fn(),
  onPickAttachment: jest.fn(),
  onSend: jest.fn(),
  onStop: jest.fn(),
  isOffline: false,
};

type HostNode = { type?: unknown; props?: Record<string, unknown>; children?: unknown[] };

/** The off-screen copy of the draft, wrapped at the field width. */
function measureCopies(root: HostNode): HostNode[] {
  const found: HostNode[] = [];
  const walk = (node: HostNode) => {
    if (node.type === "Text" && typeof node.props?.onLayout === "function") found.push(node);
    for (const child of node.children ?? []) {
      if (child && typeof child === "object") walk(child as HostNode);
    }
  };
  walk(root);
  return found;
}

const TYPED = "Plan a weekend in Lisbon";
const FIELD_WIDTH = 280;

/** The off-screen copy reports its layout the way the native text does after a keystroke. */
async function layOutCopies(field: HostNode, lines: number) {
  const copies = measureCopies(field);
  expect(copies).toHaveLength(1);
  await act(async () => {
    (copies[0]!.props?.onLayout as (event: unknown) => void)({
      nativeEvent: { layout: { x: 0, y: 0, width: FIELD_WIDTH, height: 24 * lines } },
    });
  });
}

describe("ChatComposer renders per keystroke", () => {
  it("renders once for a typed letter: the selection and the measure repeat what it already shows", async () => {
    const view = await render(
      <DraftHarness input="P">
        <ChatComposer {...props} />
      </DraftHarness>,
    );
    const input = () => view.getByTestId("chat-composer-input");
    await fireEvent(input(), "layout", {
      nativeEvent: { layout: { x: 0, y: 0, width: FIELD_WIDTH, height: 24 } },
    });
    await layOutCopies(view.getByTestId("chat-composer-field") as HostNode, 1);

    const perKeystroke: number[] = [];
    for (let length = 2; length <= TYPED.length; length += 1) {
      const before = mockComposerRenders.mock.calls.length;
      await act(async () => {
        fireEvent.changeText(input(), TYPED.slice(0, length));
      });
      await act(async () => {
        fireEvent(input(), "selectionChange", {
          nativeEvent: { selection: { start: length, end: length } },
        });
      });
      await layOutCopies(view.getByTestId("chat-composer-field") as HostNode, 1);
      perKeystroke.push(mockComposerRenders.mock.calls.length - before);
    }

    expect(input().props.value).toBe(TYPED);
    expect(new Set(perKeystroke)).toEqual(new Set([1]));
  });

  it("still renders when a keystroke moves the text onto a second line", async () => {
    const view = await render(
      <DraftHarness input="P">
        <ChatComposer {...props} />
      </DraftHarness>,
    );
    const input = () => view.getByTestId("chat-composer-input");
    await fireEvent(input(), "layout", {
      nativeEvent: { layout: { x: 0, y: 0, width: FIELD_WIDTH, height: 24 } },
    });
    await layOutCopies(view.getByTestId("chat-composer-field") as HostNode, 1);
    expect(input()).toHaveStyle({ height: 24 });

    // The text wraps onto a second line: the field grows to it.
    const wide = "x".repeat(60);
    await act(async () => {
      fireEvent.changeText(input(), wide);
    });
    const before = mockComposerRenders.mock.calls.length;
    await layOutCopies(view.getByTestId("chat-composer-field") as HostNode, 2);
    expect(mockComposerRenders.mock.calls.length).toBeGreaterThan(before);
    expect(input()).toHaveStyle({ height: 48 });
  });
});
