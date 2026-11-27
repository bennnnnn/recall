import { act, render } from "@testing-library/react-native";
import { activateKeepAwakeAsync, deactivateKeepAwake } from "expo-keep-awake";

import { useKeepAwakeWhile } from "@/hooks/useKeepAwakeWhile";
import { releaseAllScreenAwake } from "@/lib/keepAwake";
import { heldAwakeTags } from "@/lib/__tests__/support/screenAwake";
import { reportFailure } from "@/lib/sentry";

jest.mock("@/lib/sentry", () => ({ reportFailure: jest.fn() }));

function Owner({ name, on }: { name: string; on: boolean }) {
  useKeepAwakeWhile(name, on);
  return null;
}

const activate = jest.mocked(activateKeepAwakeAsync);
const deactivate = jest.mocked(deactivateKeepAwake);

describe("useKeepAwakeWhile", () => {
  beforeEach(() => {
    releaseAllScreenAwake();
    jest.clearAllMocks();
  });

  it("holds the screen on while on, and lets it sleep when off", async () => {
    const view = await render(<Owner name="live-talk" on={false} />);
    expect(activate).not.toHaveBeenCalled();

    await view.rerender(<Owner name="live-talk" on />);
    expect(activate).toHaveBeenCalledTimes(1);
    const tag = activate.mock.calls[0]![0]!;
    expect(tag).toMatch(/^live-talk:/);
    expect(heldAwakeTags()).toEqual([tag]);

    await view.rerender(<Owner name="live-talk" on={false} />);
    expect(deactivate).toHaveBeenCalledWith(tag);
    expect(heldAwakeTags()).toEqual([]);
  });

  it("lets the screen sleep when its owner unmounts", async () => {
    const view = await render(<Owner name="picture" on />);
    const tag = activate.mock.calls[0]![0]!;
    await view.unmount();
    expect(deactivate).toHaveBeenCalledWith(tag);
    expect(heldAwakeTags()).toEqual([]);
  });

  it("gives each owner its own tag: one ending keeps the other's hold", async () => {
    const talk = await render(<Owner name="live-talk" on />);
    const picture = await render(<Owner name="picture" on />);
    const [talkTag, pictureTag] = activate.mock.calls.map((call) => call[0]!);
    expect(talkTag).not.toBe(pictureTag);

    await talk.rerender(<Owner name="live-talk" on={false} />);
    expect(deactivate.mock.calls).toEqual([[talkTag]]);
    expect(heldAwakeTags()).toEqual([pictureTag]);
    await picture.unmount();
  });

  it("releases every hold at sign-out, and a later unmount releases nothing twice", async () => {
    const view = await render(
      <>
        <Owner name="dictation" on />
        <Owner name="picture" on />
      </>,
    );
    expect(heldAwakeTags()).toHaveLength(2);

    releaseAllScreenAwake();
    expect(deactivate).toHaveBeenCalledTimes(2);
    expect(heldAwakeTags()).toEqual([]);

    await view.unmount();
    expect(deactivate).toHaveBeenCalledTimes(2);
  });

  it("reports a phone that refuses, and keeps going", async () => {
    activate.mockRejectedValueOnce(new Error("Unable to activate keep awake"));
    const view = await render(<Owner name="live-talk" on />);
    // The preset's promises settle on the next turn of the loop.
    await act(() => new Promise((done) => setTimeout(done, 0)));
    expect(reportFailure).toHaveBeenCalledWith("keep_awake", expect.any(Error));
    await view.unmount();
    expect(heldAwakeTags()).toEqual([]);
  });
});
