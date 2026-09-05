import React from "react";
import { Text } from "react-native";
import { act, render } from "@testing-library/react-native";
import { useProjectActions } from "@/hooks/useProjectActions";
import { api } from "@/lib/api";
import { invalidateProjectDetail } from "@/lib/cache/projectDetailCache";
let mockSession = 1;
let mockToken = "token";
jest.mock("@/contexts/AuthContext", () => ({ useAuthToken: () => mockToken }));
jest.mock("@/lib/auth", () => ({
  getSessionGeneration: () => mockSession,
  requireTokenSession: jest.fn(),
  SessionChangedError: class extends Error {},
}));
jest.mock("@/lib/api", () => ({
  api: { createProject: jest.fn(), updateProject: jest.fn(), getProject: jest.fn() },
}));
jest.mock("@/lib/cache/projectDetailCache", () => ({ invalidateProjectDetail: jest.fn() }));
let actions: ReturnType<typeof useProjectActions>;
function Probe() {
  const result = useProjectActions();
  React.useLayoutEffect(() => {
    actions = result;
  }, [result]);
  return <Text>project actions</Text>;
}
beforeEach(() => {
  jest.clearAllMocks();
  mockSession = 1;
  mockToken = "token";
});
it("creates projects through the API", async () => {
  await render(<Probe />);
  (api.createProject as jest.Mock).mockResolvedValue({ id: "p1" });
  await actions.createProject({ title: "Spanish", kind: "language" });
  expect(api.createProject).toHaveBeenCalledWith("token", { title: "Spanish", kind: "language" });
});
it("invalidates owned detail after updating a project", async () => {
  await render(<Probe />);
  (api.updateProject as jest.Mock).mockResolvedValue({ id: "p1", daily_goal: 10 });
  await actions.updateProject("p1", { daily_goal: 10 });
  expect(invalidateProjectDetail).toHaveBeenCalledWith("p1", 1);
});
it("requests list-bearing detail for export", async () => {
  await render(<Probe />);
  (api.getProject as jest.Mock).mockResolvedValue({ id: "p1" });
  await actions.getExportProject("p1");
  expect(api.getProject).toHaveBeenCalledWith("token", "p1", { includeLists: true });
});
it("rejects retained callbacks before starting requests in another session", async () => {
  await render(<Probe />);
  const old = actions;
  mockSession++;
  await expect(old.createProject({ title: "Spanish" })).rejects.toThrow();
  expect(api.createProject).not.toHaveBeenCalled();
});
it("does not invalidate another account after a pending mutation", async () => {
  let resolve!: (value: unknown) => void;
  (api.updateProject as jest.Mock).mockReturnValue(
    new Promise((done) => {
      resolve = done;
    }),
  );
  await render(<Probe />);
  const task = actions.updateProject("p1", { daily_goal: 10 }).catch((error) => error);
  mockSession++;
  await act(async () => {
    resolve({ id: "p1" });
    await task;
  });
  expect(invalidateProjectDetail).not.toHaveBeenCalled();
});
it("accepts refresh-era callbacks for the same account", async () => {
  const ui = await render(<Probe />);
  const old = actions;
  mockToken = "refreshed";
  await ui.rerender(<Probe />);
  (api.createProject as jest.Mock).mockResolvedValue({ id: "p1" });
  await old.createProject({ title: "Spanish" });
  expect(api.createProject).toHaveBeenCalledWith("token", { title: "Spanish" });
});
