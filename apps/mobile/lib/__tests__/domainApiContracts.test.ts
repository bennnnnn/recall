jest.mock("@/lib/deviceTimezone", () => ({
  getDeviceTimezone: () => "America/Los_Angeles",
}));
jest.mock("@/lib/api/client", () => ({
  request: jest.fn(),
}));

import { attachmentRecordExists, attachmentsApi } from "@/lib/api/attachments";
import { request } from "@/lib/api/client";
import { projectsApi } from "@/lib/api/projects";

const mockRequest = request as jest.Mock;

describe("domain API contracts", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockRequest.mockResolvedValue({});
  });

  it("encodes project detail list and timezone options", async () => {
    await projectsApi.getProject("token", "p 1", { includeLists: true });
    expect(mockRequest).toHaveBeenCalledWith(
      "/projects/p 1?client_timezone=America%2FLos_Angeles&include_lists=true",
      "token",
    );
  });

  it("encodes daily item paging and bucket options", async () => {
    await projectsApi.getProjectDailyItems("token", "p1", "2026-08-21", {
      limit: 25,
      offset: 50,
      bucket: "missed",
    });
    expect(mockRequest).toHaveBeenCalledWith(
      "/projects/p1/daily-items?activity_date=2026-08-21&limit=25&offset=50&bucket=missed&client_timezone=America%2FLos_Angeles",
      "token",
    );
  });

  it("encodes gallery filters and pagination", async () => {
    await attachmentsApi.listAttachments("token", {
      category: "images",
      source: "generated",
      limit: 30,
      offset: 60,
    });
    expect(mockRequest).toHaveBeenCalledWith(
      "/attachments?category=images&source=generated&limit=30&offset=60",
      "token",
    );
  });

  it("encodes gallery search query", async () => {
    await attachmentsApi.listAttachments("token", { q: "see you later" });
    expect(mockRequest).toHaveBeenCalledWith(
      "/attachments?q=see+you+later",
      "token",
    );
  });

  it("deletes a Library attachment", async () => {
    await attachmentsApi.deleteAttachment("token", "att-1");
    expect(mockRequest).toHaveBeenCalledWith("/attachments/att-1", "token", {
      method: "DELETE",
    });
  });

  it("probes GET /url to see if a Library record still exists", async () => {
    mockRequest.mockResolvedValue({ id: "a" });
    await expect(attachmentRecordExists("token", "a")).resolves.toBe(true);
    expect(mockRequest).toHaveBeenCalledWith("/attachments/a/url", "token");

    mockRequest.mockRejectedValue(Object.assign(new Error("gone"), { status: 404 }));
    await expect(attachmentRecordExists("token", "gone")).resolves.toBe(false);

    mockRequest.mockRejectedValue(new Error("offline"));
    await expect(attachmentRecordExists("token", "a")).resolves.toBeNull();
  });

  it("uses PATCH for project item status updates", async () => {
    await projectsApi.updateProjectItem("token", "p1", "i1", { status: "mastered" });
    expect(mockRequest).toHaveBeenCalledWith("/projects/p1/items/i1", "token", {
      method: "PATCH",
      body: JSON.stringify({ status: "mastered" }),
    });
  });
});
