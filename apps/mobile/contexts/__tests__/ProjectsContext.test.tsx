import React, { useLayoutEffect } from "react";
import { Text } from "react-native";
import { act, render } from "@testing-library/react-native";
import { ProjectsProvider, useProjects } from "@/contexts/ProjectsContext";
import { api, type Project } from "@/lib/api";
let mockSession = 1;
let mockToken: string | null = "token";
jest.mock("@/contexts/AuthContext", () => ({ useAuthOptional: () => ({ token: mockToken }) }));
jest.mock("@/lib/auth", () => ({
  getSessionGeneration: () => mockSession,
  requireTokenSession: jest.fn(),
}));
jest.mock("@/lib/api", () => ({ api: { listProjects: jest.fn() } }));
let current: ReturnType<typeof useProjects>;
function Probe() {
  const value = useProjects();
  useLayoutEffect(() => {
    current = value;
  });
  return <Text>{value.projects.map((row) => row.title).join(",")}</Text>;
}
const tree = () => (
  <ProjectsProvider>
    <Probe />
  </ProjectsProvider>
);
const row = (title: string) => ({ id: "p", title, daily_goal: 5 }) as Project;
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
const fetch = jest.mocked(api.listProjects);
beforeEach(() => {
  jest.clearAllMocks();
  mockSession += 1;
  mockToken = "token";
});
it("replays independent local edits over an older GET and forces recovery after it settles", async () => {
  fetch.mockResolvedValueOnce([row("Original")]);
  await render(tree());
  const pending = deferred<Project[]>();
  fetch
    .mockReturnValueOnce(pending.promise)
    .mockResolvedValueOnce([{ ...row("Server"), daily_goal: 10 }]);
  let read!: Promise<void>;
  let recovery!: Promise<void>;
  await act(() => {
    read = current.refresh({ force: true });
    current.setProjects((rows) => rows.map((entry) => ({ ...entry, daily_goal: 10 })));
    recovery = current.refresh({ afterPending: true });
  });
  expect(current.projects[0].daily_goal).toBe(10);
  await act(async () => {
    pending.resolve([row("Original")]);
    await read;
    await recovery;
  });
  expect(current.projects[0]).toMatchObject({ title: "Server", daily_goal: 10 });
  expect(fetch).toHaveBeenCalledTimes(3);
});
it("hides old rows and rejects old responses, mutations and refresh callbacks after account changes", async () => {
  fetch.mockResolvedValueOnce([row("Old")]);
  const screen = await render(tree());
  const old = current;
  const pending = deferred<Project[]>();
  fetch.mockReturnValueOnce(pending.promise).mockResolvedValueOnce([row("New")]);
  let read!: Promise<void>;
  await act(() => {
    read = current.refresh({ force: true });
  });
  mockSession += 1;
  mockToken = "other";
  await screen.rerender(tree());
  await act(async () => {
    old.setProjects([row("Leak")]);
    await old.refresh();
    pending.resolve([row("Late")]);
    await read;
  });
  expect(current.projects.map((entry) => entry.title)).toEqual(["New"]);
  expect(fetch).toHaveBeenCalledTimes(3);
});
it("preserves rows during token refresh and exposes refresh errors with cached content", async () => {
  fetch.mockResolvedValueOnce([row("Class")]);
  const screen = await render(tree());
  mockToken = "refreshed";
  await screen.rerender(tree());
  expect(fetch).toHaveBeenCalledTimes(1);
  fetch.mockRejectedValueOnce(new Error("offline"));
  await act(() => current.refresh({ force: true }));
  expect(fetch).toHaveBeenLastCalledWith("refreshed");
  expect(current.error).toBe(true);
  expect(current.projects[0].title).toBe("Class");
});
