import { act, render } from "@testing-library/react-native";

import { DrawerShell } from "@/features/chat/drawer/DrawerShell";
import { useDrawerControls, useDrawerOpen } from "@/contexts/DrawerContext";
import { closeDrawer, openDrawer } from "@/features/chat/drawer/drawer";

jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => 1 }));
jest.mock("@/features/chat/drawer/ConversationList", () => ({ ConversationList: () => null }));

const screenRendered = jest.fn<void, [ReturnType<typeof useDrawerControls>]>();
const readerRendered = jest.fn<void, [boolean]>();

/** Stands in for the chat screen: it holds the controls but not the open state. */
function Screen() {
  screenRendered(useDrawerControls());
  return <OpenReader />;
}

/** Stands in for the composer or the header: it draws differently while the drawer is open. */
function OpenReader() {
  readerRendered(useDrawerOpen());
  return null;
}

const controls = () => screenRendered.mock.calls.at(-1)![0];
const renders = () => ({
  screen: screenRendered.mock.calls.length,
  reader: readerRendered.mock.calls.length,
  readerSawOpen: readerRendered.mock.calls.at(-1)?.[0],
});

describe("DrawerShell", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("re-renders only the readers of the open state when the drawer opens or closes", async () => {
    await render(
      <DrawerShell>
        <Screen />
      </DrawerShell>,
    );
    const initialControls = controls();
    expect(renders()).toEqual({ screen: 1, reader: 1, readerSawOpen: false });

    await act(async () => openDrawer());
    expect(controls().isOpenNow()).toBe(true);
    expect(renders()).toEqual({ screen: 1, reader: 2, readerSawOpen: true });

    await act(async () => closeDrawer());
    expect(controls().isOpenNow()).toBe(false);
    expect(renders()).toEqual({ screen: 1, reader: 3, readerSawOpen: false });
    expect(controls()).toBe(initialControls);
  });

  it("answers isOpenNow before React has rendered the change", async () => {
    await render(
      <DrawerShell>
        <Screen />
      </DrawerShell>,
    );
    let seenInsideTheSameTask: boolean | null = null;
    await act(async () => {
      openDrawer();
      seenInsideTheSameTask = controls().isOpenNow();
    });
    expect(seenInsideTheSameTask).toBe(true);
  });
});
