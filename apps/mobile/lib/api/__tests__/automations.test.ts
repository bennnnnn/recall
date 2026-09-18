import { automationsApi } from "@/lib/api/automations";
import { request } from "@/lib/api/client";

jest.mock("@/lib/api/client", () => ({ request: jest.fn() }));

beforeEach(() => jest.resetAllMocks());

it("lists automations", async () => {
  jest.mocked(request).mockResolvedValue([]);
  await automationsApi.listAutomations("token");
  expect(request).toHaveBeenCalledWith("/automations", "token");
});

it("gets one automation", async () => {
  jest.mocked(request).mockResolvedValue({});
  await automationsApi.getAutomation("token", "auto-1");
  expect(request).toHaveBeenCalledWith("/automations/auto-1", "token");
});

it("creates an automation with snake_case body fields", async () => {
  jest.mocked(request).mockResolvedValue({ id: "auto-1" });
  await automationsApi.createAutomation("token", {
    prompt: "Find L3 backend jobs",
    frequency: "daily",
    nextRunAt: "2026-09-18T15:00:00.000Z",
  });
  const [path, token, init] = jest.mocked(request).mock.calls[0];
  expect(path).toBe("/automations");
  expect(token).toBe("token");
  expect(init).toMatchObject({ method: "POST" });
  expect(JSON.parse(init!.body as string)).toEqual({
    title: null,
    prompt: "Find L3 backend jobs",
    frequency: "daily",
    next_run_at: "2026-09-18T15:00:00.000Z",
  });
});

it("patches only the provided fields on update", async () => {
  jest.mocked(request).mockResolvedValue({ id: "auto-1" });
  await automationsApi.updateAutomation("token", "auto-1", { status: "paused" });
  expect(request).toHaveBeenCalledWith("/automations/auto-1", "token", {
    method: "PATCH",
    body: JSON.stringify({ status: "paused" }),
  });
});

it("deletes an automation", async () => {
  jest.mocked(request).mockResolvedValue(undefined);
  await automationsApi.deleteAutomation("token", "auto-1");
  expect(request).toHaveBeenCalledWith("/automations/auto-1", "token", { method: "DELETE" });
});
