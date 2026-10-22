import { AppState } from "react-native";

import { onAppStateChange } from "@/lib/foregroundRefresh";

const handlers: ((state: string) => void)[] = [];
const removed = jest.fn();
jest.mock("react-native", () => ({
  AppState: {
    addEventListener: jest.fn((_event: string, handler: (state: string) => void) => {
      handlers.push(handler);
      return { remove: () => { removed(); handlers.splice(handlers.indexOf(handler), 1); } };
    }),
  },
}));

it("fans one native AppState listener out to every subscriber (NET-16)", () => {
  const first = jest.fn();
  const second = jest.fn();
  const stopFirst = onAppStateChange(first);
  const stopSecond = onAppStateChange(second);
  expect(AppState.addEventListener).toHaveBeenCalledTimes(1);

  handlers[0]("active");
  expect(first).toHaveBeenCalledWith("active");
  expect(second).toHaveBeenCalledWith("active");

  stopFirst();
  handlers[0]("background");
  expect(first).toHaveBeenCalledTimes(1);
  expect(second).toHaveBeenCalledWith("background");

  // The last one out removes the native listener; the next one in adds it again.
  stopSecond();
  expect(removed).toHaveBeenCalledTimes(1);
  expect(handlers).toHaveLength(0);
  const stopThird = onAppStateChange(jest.fn());
  expect(AppState.addEventListener).toHaveBeenCalledTimes(2);
  stopThird();
});
