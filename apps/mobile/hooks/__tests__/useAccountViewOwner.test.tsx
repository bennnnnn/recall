import { useEffect, useLayoutEffect } from "react";
import { render } from "@testing-library/react-native";

import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";

let mockFocused = true;
let mockToken: string | null = "token-a";
let mockSession = 1;

jest.mock("expo-router", () => ({
  useFocusEffect: (effect: () => void | (() => void)) => {
    const React = jest.requireActual("react");
    const focused = mockFocused;
    React.useEffect(() => (focused ? effect() : undefined), [effect, focused]);
  },
}));
jest.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ token: mockToken }) }));
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));

let mounts = 0;
let latestIsCurrent: () => boolean = () => false;

function Content({ isCurrent }: { isCurrent: () => boolean }) {
  useLayoutEffect(() => {
    latestIsCurrent = isCurrent;
  });
  useEffect(() => {
    mounts += 1;
  }, []);
  return null;
}

function Screen() {
  const view = useAccountViewOwner();
  return <Content key={view.key} isCurrent={view.isCurrent} />;
}

beforeEach(() => {
  mockFocused = true;
  mockToken = "token-a";
  mockSession = 1;
  mounts = 0;
});

it("keeps the screen mounted across a blur and return, and ends the visit while away", async () => {
  const screen = await render(<Screen />);
  expect(mounts).toBe(1);
  expect(latestIsCurrent()).toBe(true);

  mockFocused = false;
  await screen.rerender(<Screen />);
  expect(latestIsCurrent()).toBe(false);

  mockFocused = true;
  await screen.rerender(<Screen />);
  // The old key held the visit: each blur and return mounted the page again (scroll reset).
  expect(mounts).toBe(1);
  expect(latestIsCurrent()).toBe(true);
});

it("mounts the screen again for another sign-in", async () => {
  const screen = await render(<Screen />);
  expect(mounts).toBe(1);
  mockSession = 2;
  mockToken = "token-b";
  await screen.rerender(<Screen />);
  expect(mounts).toBe(2);
  expect(latestIsCurrent()).toBe(true);
});

it("ends a visit's callbacks once the account signs out", async () => {
  const screen = await render(<Screen />);
  const firstVisit = latestIsCurrent;
  mockSession = 2;
  mockToken = null;
  await screen.rerender(<Screen />);
  expect(firstVisit()).toBe(false);
  expect(latestIsCurrent()).toBe(false);
});
