import React from "react";
import { Text } from "react-native";
import { act, render } from "@testing-library/react-native";

import { useProjectActions } from "@/hooks/useProjectActions";

jest.mock("@/contexts/AuthContext", () => ({
  useAuthToken: () => "token",
}));
jest.mock("@/lib/api", () => ({
  api: {
    createProject: jest.fn(),
    updateProject: jest.fn(),
    updateProjectItem: jest.fn(),
    deleteProject: jest.fn(),
    getProject: jest.fn(),
  },
}));
jest.mock("@/lib/cache/projectDetailCache", () => ({
  invalidateProjectDetail: jest.fn(),
}));

import { api } from "@/lib/api";
import { invalidateProjectDetail } from "@/lib/cache/projectDetailCache";

let actions: ReturnType<typeof useProjectActions>;

function Probe() {
  actions = useProjectActions();
  return <Text>project actions</Text>;
}

beforeEach(async () => {
  jest.clearAllMocks();
  await act(async () => {
    render(<Probe />);
  });
});

describe("useProjectActions", () => {
  it("creates projects through the projects API", async () => {
    (api.createProject as jest.Mock).mockResolvedValue({ id: "p1" });
    await act(async () => {
      await actions.createProject({ title: "Spanish", kind: "language" });
    });
    expect(api.createProject).toHaveBeenCalledWith("token", {
      title: "Spanish",
      kind: "language",
    });
  });

  it("invalidates detail after updating a project item", async () => {
    (api.updateProjectItem as jest.Mock).mockResolvedValue({ id: "i1", status: "mastered" });
    await act(async () => {
      await actions.updateProjectItem("p1", "i1", "mastered");
    });
    expect(api.updateProjectItem).toHaveBeenCalledWith("token", "p1", "i1", {
      status: "mastered",
    });
    expect(invalidateProjectDetail).toHaveBeenCalledWith("p1");
  });

  it("requests list-bearing detail for export", async () => {
    (api.getProject as jest.Mock).mockResolvedValue({ id: "p1" });
    await act(async () => {
      await actions.getExportProject("p1");
    });
    expect(api.getProject).toHaveBeenCalledWith("token", "p1", { includeLists: true });
  });
});
